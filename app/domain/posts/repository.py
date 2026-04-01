# 게시글·post_images 데이터 접근. ORM은 .model 참조.
from __future__ import annotations

from sqlalchemy import delete, exists, false, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.db.base_class import utc_now
from app.users.model import DogProfile, User, UserBlock

from .model import Category, Hashtag, Post, PostImage, post_hashtags


def _apply_post_list_search_filter(stmt, *, search_q: str | None):
    """목록/카운트 공통: #태그면 M:N 정확 매칭, 아니면 제목·본문 ILIKE."""
    if not search_q or not (raw := search_q.strip()):
        return stmt
    if raw.startswith("#"):
        tag_name = raw.lstrip("#").strip().lower()
        if not tag_name:
            return stmt.where(false())
        hb = exists(
            select(literal(1))
            .select_from(post_hashtags)
            .join(Hashtag, Hashtag.id == post_hashtags.c.hashtag_id)
            .where(
                post_hashtags.c.post_id == Post.id,
                Hashtag.name == tag_name,
            )
        )
        return stmt.where(hb)
    pattern = f"%{raw}%"
    return stmt.where(or_(Post.title.ilike(pattern), Post.content.ilike(pattern)))


class PostsModel:
    MAX_POST_IMAGES = 5

    @classmethod
    async def category_exists(cls, category_id: int, *, db: AsyncSession) -> bool:
        r = await db.execute(select(exists().where(Category.id == category_id)))
        return bool(r.scalar())

    @classmethod
    async def sync_post_hashtags(
        cls,
        post_id: str,
        hashtag_names: list[str],
        *,
        db: AsyncSession,
    ) -> None:
        await db.execute(delete(post_hashtags).where(post_hashtags.c.post_id == post_id))

        if not hashtag_names:
            return

        result = await db.execute(
            select(Hashtag.id, Hashtag.name).where(Hashtag.name.in_(hashtag_names))
        )
        existing_by_name = {row[1]: row[0] for row in result.all()}
        missing = set(hashtag_names) - set(existing_by_name.keys())

        if missing:
            await db.execute(
                pg_insert(Hashtag)
                .values([{"name": n} for n in missing])
                .on_conflict_do_nothing(index_elements=[Hashtag.name])
            )

        result2 = await db.execute(
            select(Hashtag.id, Hashtag.name).where(Hashtag.name.in_(hashtag_names))
        )
        existing_by_name = {row[1]: row[0] for row in result2.all()}
        hashtag_ids = [existing_by_name[n] for n in hashtag_names if n in existing_by_name]

        if hashtag_ids:
            await db.execute(
                pg_insert(post_hashtags)
                .values([{"post_id": post_id, "hashtag_id": hid} for hid in hashtag_ids])
                .on_conflict_do_nothing(index_elements=["post_id", "hashtag_id"])
            )

    @classmethod
    async def create_post(
        cls,
        user_id: str,
        title: str,
        content: str,
        image_ids: list[str] | None = None,
        category_id: int | None = None,
        hashtag_names: list[str] | None = None,
        *,
        db: AsyncSession,
    ) -> str:
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
        post_id: str,
        db: AsyncSession,
        current_user_id: str | None = None,
    ) -> Post | None:
        stmt = (
            select(Post)
            .where(
                Post.id == post_id,
                Post.deleted_at.is_(None),
                Post.is_blinded.is_(False),
            )
            .options(
                joinedload(Post.user).options(
                    joinedload(User.profile_image),
                    selectinload(User.dogs).joinedload(DogProfile.profile_image),
                ),
                joinedload(Post.category),
                selectinload(Post.hashtags),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
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
        post_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> tuple[Post, bool] | None:
        from app.likes.model import PostLike

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
            .options(
                joinedload(Post.user).options(
                    joinedload(User.profile_image),
                    selectinload(User.dogs).joinedload(DogProfile.profile_image),
                ),
                joinedload(Post.category),
                selectinload(Post.hashtags),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
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
    async def get_post_author_id(cls, post_id: str, db: AsyncSession) -> str | None:
        result = await db.execute(
            select(Post.user_id).where(Post.id == post_id, Post.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_titles_by_ids(cls, post_ids: list[str], db: AsyncSession) -> dict[str, str]:
        if not post_ids:
            return {}
        result = await db.execute(
            select(Post.id, Post.title).where(Post.id.in_(post_ids), Post.deleted_at.is_(None))
        )
        return {row[0]: row[1] for row in result.all()}

    @classmethod
    async def get_all_posts(
        cls,
        page: int = 1,
        size: int = 20,
        *,
        db: AsyncSession,
        search_q: str | None = None,
        category_id: int | None = None,
        current_user_id: str | None = None,
    ) -> tuple[list[Post], bool]:
        offset = (page - 1) * size
        fetch_limit = size + 1
        stmt = (
            select(Post)
            .where(Post.deleted_at.is_(None), Post.is_blinded.is_(False))
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
                joinedload(Post.category),
                selectinload(Post.hashtags),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
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
        stmt = stmt.order_by(Post.created_at.desc())
        stmt = stmt.limit(fetch_limit).offset(offset)
        result = await db.execute(stmt)
        rows = result.unique().scalars().all()
        has_more = len(rows) > size
        return list(rows[:size]), has_more

    @classmethod
    async def get_posts_count(
        cls,
        *,
        db: AsyncSession,
        search_q: str | None = None,
        category_id: int | None = None,
        current_user_id: str | None = None,
    ) -> int:
        stmt = select(func.count(Post.id)).where(
            Post.deleted_at.is_(None), Post.is_blinded.is_(False)
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
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return row or 0

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
    async def update_post(
        cls,
        post_id: str,
        title: str | None = None,
        content: str | None = None,
        image_ids: list[str] | None = None,
        category_id: int | None = None,
        hashtag_names: list[str] | None = None,
        *,
        db: AsyncSession,
    ) -> tuple[list[str], list[str]] | None:
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

        released_ids: list[str] = []
        added_ids: list[str] = []
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
    async def delete_post(cls, post_id: str, db: AsyncSession) -> tuple[bool, list[str]]:
        from app.comments.model import Comment
        from app.likes.model import PostLikesModel

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
    async def increment_view_count(cls, post_id: str, db: AsyncSession) -> bool:
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
    async def increment_view_count_delta(cls, post_id: str, delta: int, db: AsyncSession) -> bool:
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
    async def increment_report_count(cls, post_id: str, db: AsyncSession) -> int | None:
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
    async def set_blinded(cls, post_id: str, db: AsyncSession) -> bool:
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
    async def unblind_post(cls, post_id: str, db: AsyncSession) -> bool:
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
    async def reset_reports(cls, post_id: str, db: AsyncSession) -> bool:
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
    async def get_reported_posts(
        cls,
        page: int = 1,
        size: int = 20,
        *,
        db: AsyncSession,
    ) -> tuple[list[Post], int]:
        offset = (page - 1) * size
        stmt_base = (
            select(Post)
            .where(Post.deleted_at.is_(None))
            .where(Post.report_count > 0)
            .options(
                joinedload(Post.user).joinedload(User.profile_image),
                joinedload(Post.user).selectinload(User.dogs).joinedload(DogProfile.profile_image),
                joinedload(Post.category),
                selectinload(Post.hashtags),
                selectinload(Post.post_images).joinedload(PostImage.image),
            )
            .order_by(Post.report_count.desc(), Post.created_at.desc())
        )
        count_stmt = (
            select(func.count(Post.id))
            .where(Post.deleted_at.is_(None))
            .where(Post.report_count > 0)
        )
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        stmt = stmt_base.limit(size).offset(offset)
        result = await db.execute(stmt)
        posts = list(result.unique().scalars().all())
        return posts, total

    @classmethod
    async def get_like_count(cls, post_id: str, db: AsyncSession) -> int:
        result = await db.execute(select(Post.like_count).where(Post.id == post_id))
        row = result.scalar_one_or_none()
        return row or 0

    @classmethod
    async def increment_like_count(cls, post_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1, updated_at=utc_now())
            .returning(Post.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def decrement_like_count(cls, post_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=func.greatest(Post.like_count - 1, 0), updated_at=utc_now())
            .returning(Post.like_count)
        )
        row = result.one_or_none()
        return row[0] if row is not None else 0

    @classmethod
    async def increment_comment_count(cls, post_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + 1, updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def decrement_comment_count(cls, post_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=func.greatest(Post.comment_count - 1, 0), updated_at=utc_now())
            .returning(Post.id)
        )
        return result.scalar_one_or_none() is not None
