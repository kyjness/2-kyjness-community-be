# 게시글·post_images 데이터 접근. ORM은 .model 참조.

from datetime import timedelta
from uuid import UUID

from sqlalchemy import Select, and_, delete, exists, false, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.common.exceptions import InvalidRequestException
from app.db.base_class import utc_now
from app.domain.users.model import DogProfile, User, UserBlock

from .model import Category, Hashtag, Post, PostImage, post_hashtags

# pg_trgm: 라틴 3자 미만·한글 1음절·숫자 1자리는 인덱스 효율 저하 → 앱 레벨 거부.
POST_SEARCH_MIN_TOKEN_LEN = 3
_POST_SEARCH_MIN_TOKEN_LEN_HANGUL = 2
_POST_SEARCH_MIN_TOKEN_LEN_DIGIT = 2


def tokenize_search_query(raw: str) -> list[str]:
    return [part for part in raw.split() if part]


def _min_token_length(token: str) -> int:
    if any("\uac00" <= ch <= "\ud7a3" for ch in token):
        return _POST_SEARCH_MIN_TOKEN_LEN_HANGUL
    if token.isdigit():
        return _POST_SEARCH_MIN_TOKEN_LEN_DIGIT
    return POST_SEARCH_MIN_TOKEN_LEN


def _is_token_too_short(token: str) -> bool:
    return len(token) < _min_token_length(token)


def validate_search_query(q: str | None) -> str | None:
    """검색어 정규화·길이 검증. #태그는 정확 매칭(길이 제한 별도)."""
    if not q or not (stripped := q.strip()):
        return None
    if stripped.startswith("#"):
        tag_name = stripped.lstrip("#").strip().lower()
        if not tag_name:
            raise InvalidRequestException("검색할 해시태그를 입력해주세요.")
        return stripped
    tokens = tokenize_search_query(stripped)
    if not tokens:
        return None
    if any(_is_token_too_short(t) for t in tokens):
        raise InvalidRequestException(
            "검색어는 공백으로 구분된 각 단어가 최소 2글자(한글·숫자) 또는 3글자(영문) 이상이어야 합니다."
        )
    return stripped


def _hashtag_exact_exists(tag_name: str):
    return exists(
        select(literal(1))
        .select_from(post_hashtags)
        .join(Hashtag, Hashtag.id == post_hashtags.c.hashtag_id)
        .where(
            post_hashtags.c.post_id == Post.id,
            Hashtag.name == tag_name,
        )
    )


_ILIKE_ESCAPE = "\\"


def _escape_ilike_token(token: str) -> str:
    """ILIKE 와일드카드 문자(%, _)와 이스케이프 문자 자체를 이스케이프한다."""
    return token.replace(_ILIKE_ESCAPE, _ILIKE_ESCAPE * 2).replace("%", "\\%").replace("_", "\\_")


def _hashtag_partial_exists(pattern: str):
    return exists(
        select(literal(1))
        .select_from(post_hashtags)
        .join(Hashtag, Hashtag.id == post_hashtags.c.hashtag_id)
        .where(
            post_hashtags.c.post_id == Post.id,
            Hashtag.name.ilike(pattern, escape=_ILIKE_ESCAPE),
        )
    )


def _token_match_clause(token: str):
    """단일 토큰: 제목 OR 본문 OR 해시태그명 부분 일치.

    EXPLAIN 검증 예:
      EXPLAIN (ANALYZE, BUFFERS)
      SELECT id FROM posts
      WHERE deleted_at IS NULL AND is_blinded = false
        AND (title ILIKE '%불닭%' OR content ILIKE '%불닭%');
    → Bitmap Index Scan on idx_posts_title_gin / idx_posts_content_gin (pg_trgm 활성 시).
    """
    pattern = f"%{_escape_ilike_token(token)}%"
    return or_(
        Post.title.ilike(pattern, escape=_ILIKE_ESCAPE),
        Post.content.ilike(pattern, escape=_ILIKE_ESCAPE),
        _hashtag_partial_exists(pattern),
    )


def _apply_post_list_search_filter(stmt, *, search_q: str | None):
    """목록/카운트 공통: #태그 정확 매칭, 그 외 토큰 AND + ILIKE(pg_trgm GIN 활용)."""
    if not search_q or not (raw := search_q.strip()):
        return stmt
    if raw.startswith("#"):
        tag_name = raw.lstrip("#").strip().lower()
        if not tag_name:
            return stmt.where(false())
        return stmt.where(_hashtag_exact_exists(tag_name))
    tokens = tokenize_search_query(raw)
    if not tokens:
        return stmt
    return stmt.where(and_(*(_token_match_clause(token) for token in tokens)))


def _post_author_and_content_loads():
    """목록·상세 공통 eager load. 작성자 강아지는 대표견 1마리만 로드한다.

    응답은 author.representative_dog 하나만 쓰므로, 대표견 전용 뷰 관계로 로드한다.
    dogs를 .and_() 필터로 로드하면 컬렉션 자체가 잘려 세션에 캐시되는 트랩이 있어
    (전체 dogs를 기대하는 다른 경로가 truncate된 값을 보게 됨), dogs는 건드리지 않는다.
    """
    return (
        joinedload(Post.user).options(
            joinedload(User.profile_image),
            selectinload(User.representative_dog).joinedload(DogProfile.profile_image),
        ),
        joinedload(Post.category),
        selectinload(Post.hashtags),
        selectinload(Post.post_images).joinedload(PostImage.image),
    )


class PostsModel:
    MAX_POST_IMAGES = 5

    @classmethod
    async def category_exists(cls, category_id: int, *, db: AsyncSession) -> bool:
        r = await db.execute(select(exists().where(Category.id == category_id)))
        return bool(r.scalar())

    @classmethod
    async def post_is_visible(
        cls,
        post_id: UUID,
        *,
        db: AsyncSession,
        current_user_id: UUID | None = None,
    ) -> bool:
        """삭제·블라인드·차단 관계만 확인. 상세 조회용 eager load 없음."""
        visible_where = [
            Post.id == post_id,
            Post.deleted_at.is_(None),
            Post.is_blinded.is_(False),
        ]
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Post.user_id,
            )
            visible_where.append(~block_exists)
        r = await db.execute(select(exists().where(*visible_where)))
        return bool(r.scalar())

    @classmethod
    async def sync_post_hashtags(
        cls,
        post_id: UUID,
        hashtag_names: list[str],
        *,
        db: AsyncSession,
    ) -> None:
        await db.execute(delete(post_hashtags).where(post_hashtags.c.post_id == post_id))

        if not hashtag_names:
            return

        # 전체 이름을 멱등 upsert 후 id를 한 번에 조회한다. ON CONFLICT DO NOTHING의
        # RETURNING은 충돌(기존)분을 돌려주지 않으므로, 재조회 대신 upsert→SELECT 순으로
        # 두면 동시 삽입분까지 committed 상태로 모두 잡혀 태그 누락이 없다(5→4왕복).
        await db.execute(
            pg_insert(Hashtag)
            .values([{"name": n} for n in hashtag_names])
            .on_conflict_do_nothing(index_elements=[Hashtag.name])
        )
        rows = (
            await db.execute(
                select(Hashtag.id, Hashtag.name).where(Hashtag.name.in_(hashtag_names))
            )
        ).all()
        id_by_name = {name: hid for hid, name in rows}
        hashtag_ids = [id_by_name[n] for n in hashtag_names if n in id_by_name]

        if hashtag_ids:
            await db.execute(
                pg_insert(post_hashtags)
                .values([{"post_id": post_id, "hashtag_id": hid} for hid in hashtag_ids])
                .on_conflict_do_nothing(index_elements=["post_id", "hashtag_id"])
            )

    @classmethod
    async def create_post(
        cls,
        user_id: UUID,
        title: str,
        content: str,
        image_ids: list[UUID] | None = None,
        category_id: int | None = None,
        hashtag_names: list[str] | None = None,
        *,
        db: AsyncSession,
    ) -> UUID:
        image_ids = image_ids or []
        now = utc_now()
        post = Post(
            user_id=user_id,
            title=title,
            content=content,
            category_id=category_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db.add(post)
        await db.flush()
        limited = image_ids[: cls.MAX_POST_IMAGES]
        if limited:
            db.add_all(PostImage(post_id=post.id, image_id=iid, created_at=now) for iid in limited)
        if hashtag_names is not None:
            await cls.sync_post_hashtags(post.id, hashtag_names, db=db)
        return post.id

    @classmethod
    async def get_post_by_id(
        cls,
        post_id: UUID,
        db: AsyncSession,
        current_user_id: UUID | None = None,
    ) -> Post | None:
        stmt = (
            select(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
                Post.is_blinded.is_(False),
            )
            .options(*_post_author_and_content_loads())
        )
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Post.user_id,
            )
            stmt = stmt.where(~block_exists)
        result = await db.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_post_by_id_with_like_flag(
        cls,
        post_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> tuple[Post, bool] | None:
        from app.domain.likes.model import PostLike

        is_liked_expr = (
            exists(1).where(PostLike.post_id == Post.id, PostLike.user_id == user_id)
        ).label("is_liked")
        stmt = (
            select(Post, is_liked_expr)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
                Post.is_blinded.is_(False),
            )
            .options(*_post_author_and_content_loads())
        )
        block_exists = exists(1).where(
            UserBlock.blocker_id == user_id,
            UserBlock.blocked_id == Post.user_id,
        )
        stmt = stmt.where(~block_exists)
        result = await db.execute(stmt)
        row = result.unique().one_or_none()
        if row is None:
            return None
        return row[0], bool(row[1])

    @classmethod
    async def get_post_author_id(cls, post_id: UUID, db: AsyncSession) -> UUID | None:
        result = await db.execute(
            select(Post.user_id).where(Post.id == post_id, Post.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_titles_by_ids(cls, post_ids: list[UUID], db: AsyncSession) -> dict[UUID, str]:
        if not post_ids:
            return {}
        result = await db.execute(
            select(Post.id, Post.title).where(Post.id.in_(post_ids), Post.deleted_at.is_(None))
        )
        return {row[0]: row[1] for row in result.all()}

    @classmethod
    async def get_all_posts(
        cls,
        size: int = 20,
        *,
        db: AsyncSession,
        cursor: UUID | None = None,
        search_q: str | None = None,
        category_id: int | None = None,
        current_user_id: UUID | None = None,
    ) -> list[Post]:
        # UUIDv7 PK: ORDER BY id DESC + id < cursor는 PK B-Tree만으로 범위 스캔(추가 인덱스 불필요).
        fetch_limit = size + 1
        stmt = (
            select(Post)
            .where(Post.deleted_at.is_(None), Post.is_blinded.is_(False))
            .options(*_post_author_and_content_loads())
        )
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Post.user_id,
            )
            stmt = stmt.where(~block_exists)
        stmt = _apply_post_list_search_filter(stmt, search_q=search_q)
        if category_id is not None:
            stmt = stmt.where(Post.category_id == category_id)
        if cursor is not None:
            stmt = stmt.where(Post.id < cursor)
        stmt = stmt.order_by(Post.id.desc())
        stmt = stmt.limit(fetch_limit)
        result = await db.execute(stmt)
        rows = result.unique().scalars().all()
        return list(rows)

    @classmethod
    async def get_trending_hashtags(
        cls,
        *,
        db: AsyncSession,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        count_expr = func.count(post_hashtags.c.post_id).label("count")
        stmt = (
            select(Hashtag.name, count_expr)
            .join(post_hashtags, Hashtag.id == post_hashtags.c.hashtag_id)
            .join(Post, Post.id == post_hashtags.c.post_id)
            .where(Post.deleted_at.is_(None), Post.is_blinded.is_(False))
            .group_by(Hashtag.id, Hashtag.name)
            .order_by(count_expr.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        return [(str(r[0]), int(r[1] or 0)) for r in rows]

    @classmethod
    def get_trending_posts_query(
        cls,
        *,
        window_hours: int | None = 24,
        category_id: int | None = None,
        current_user_id: UUID | None = None,
        limit: int = 10,
        use_time_decay: bool = True,
    ) -> Select[tuple[Post]]:
        # created_at 하한을 최상단에 두어 idx_posts_feed_latest(created_at DESC, partial) 범위 스캔 유도.
        # window_hours=None 이면 기간 제한 없음(최종 fallback용).
        stmt = select(Post).where(
            Post.deleted_at.is_(None),
            Post.is_blinded.is_(False),
        )
        if window_hours is not None:
            cutoff = utc_now() - timedelta(hours=window_hours)
            stmt = stmt.where(Post.created_at >= cutoff)
        stmt = stmt.options(selectinload(Post.category))
        if category_id is not None:
            stmt = stmt.where(Post.category_id == category_id)
        if current_user_id is not None:
            block_exists = exists(1).where(
                UserBlock.blocker_id == current_user_id,
                UserBlock.blocked_id == Post.user_id,
            )
            stmt = stmt.where(~block_exists)

        if use_time_decay:
            age_hours = func.extract("epoch", func.now() - Post.created_at) / 3600.0
            score = (
                Post.comment_count * 3 + Post.like_count * 2 + Post.view_count * 0.1
            ) / func.power(age_hours + 2, 1.3)
            stmt = stmt.order_by(score.desc(), Post.id.desc())
        else:
            stmt = stmt.order_by(
                Post.like_count.desc(),
                Post.comment_count.desc(),
                Post.id.desc(),
            )

        return stmt.limit(limit)

    @classmethod
    async def get_trending_posts(
        cls,
        *,
        db: AsyncSession,
        window_hours: int | None = 24,
        category_id: int | None = None,
        current_user_id: UUID | None = None,
        limit: int = 10,
        use_time_decay: bool = True,
    ) -> list[Post]:
        stmt = cls.get_trending_posts_query(
            window_hours=window_hours,
            category_id=category_id,
            current_user_id=current_user_id,
            limit=limit,
            use_time_decay=use_time_decay,
        )
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())

    @classmethod
    async def update_post(
        cls,
        post_id: UUID,
        title: str | None = None,
        content: str | None = None,
        image_ids: list[UUID] | None = None,
        category_id: int | None = None,
        hashtag_names: list[str] | None = None,
        *,
        db: AsyncSession,
    ) -> tuple[list[UUID], list[UUID]] | None:
        now = utc_now()
        post_obj = (
            await db.execute(
                select(Post).where(
                    Post.id == post_id,
                    Post.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if post_obj is None:
            return None

        if title is not None:
            post_obj.title = title
        if content is not None:
            post_obj.content = content
        if category_id is not None:
            post_obj.category_id = category_id
        post_obj.updated_at = now

        if hashtag_names is not None:
            await cls.sync_post_hashtags(post_id, hashtag_names, db=db)

        released_ids: list[UUID] = []
        added_ids: list[UUID] = []
        if image_ids is not None:
            old_result = await db.execute(
                select(PostImage.image_id).where(PostImage.post_id == post_id)
            )
            old = old_result.scalars().all()
            old_image_ids = set(old) if old else set()
            new_image_ids_set = set(image_ids[: cls.MAX_POST_IMAGES])
            to_add = new_image_ids_set - old_image_ids
            released_ids = list(old_image_ids - new_image_ids_set)
            if to_add:
                to_add_list = list(to_add)
                added_ids = to_add_list
                db.add_all(
                    PostImage(post_id=post_id, image_id=iid, created_at=now) for iid in to_add_list
                )
            if released_ids:
                await db.execute(
                    delete(PostImage).where(
                        PostImage.post_id == post_id, PostImage.image_id.in_(released_ids)
                    )
                )
        return released_ids, added_ids

    @classmethod
    async def delete_post(cls, post_id: UUID, db: AsyncSession) -> tuple[bool, list[UUID]]:
        from app.domain.comments.model import Comment
        from app.domain.likes.model import PostLikesModel

        r_post = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(deleted_at=utc_now(), updated_at=utc_now())
            .returning(Post.id)
        )
        if r_post.scalar_one_or_none() is None:
            return (False, [])

        await db.execute(
            update(Comment)
            .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .values(deleted_at=utc_now())
        )
        await PostLikesModel.delete_by_post_id(post_id, db=db)
        r_img = await db.execute(
            delete(PostImage).where(PostImage.post_id == post_id).returning(PostImage.image_id)
        )
        image_ids = list(r_img.scalars().all()) or []
        return (True, image_ids)

    @classmethod
    async def increment_view_count(cls, post_id: UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(view_count=Post.view_count + 1, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def increment_view_count_delta(cls, post_id: UUID, delta: int, db: AsyncSession) -> bool:
        if delta <= 0:
            return True
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(view_count=Post.view_count + delta, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def increment_report_count(cls, post_id: UUID, db: AsyncSession) -> int | None:
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(report_count=Post.report_count + 1, updated_at=utc_now())
            .returning(Post.report_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else None

    @classmethod
    async def set_blinded(cls, post_id: UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(is_blinded=True, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def unblind_post(cls, post_id: UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(is_blinded=False, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def reset_reports(cls, post_id: UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
            )
            .values(report_count=0, is_blinded=False, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def get_reported_by_ids(cls, post_ids: list[UUID], db: AsyncSession) -> list[Post]:
        """신고 목록 하이드레이션용 id 배치 조회. 응답은 제목·본문·작성자만 쓰므로
        작성자+프로필 이미지만 eager-load 한다(정렬·페이지는 UNION 쿼리가 담당)."""
        if not post_ids:
            return []
        result = await db.execute(
            select(Post)
            .where(Post.id.in_(post_ids))
            .options(joinedload(Post.user).joinedload(User.profile_image))
        )
        return list(result.unique().scalars().all())

    @classmethod
    async def get_like_count(cls, post_id: UUID, db: AsyncSession) -> int:
        result = await db.execute(select(Post.like_count).where(Post.id == post_id))
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def increment_like_count(cls, post_id: UUID, db: AsyncSession) -> int:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1, updated_at=utc_now())
            .returning(Post.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def decrement_like_count(cls, post_id: UUID, db: AsyncSession) -> int:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=func.greatest(Post.like_count - 1, 0), updated_at=utc_now())
            .returning(Post.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def increment_comment_count(cls, post_id: UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + 1, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def decrement_comment_count(cls, post_id: UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=func.greatest(Post.comment_count - 1, 0), updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None
