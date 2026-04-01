# 관리자 전용: 신고 게시글/댓글 목록·블라인드 해제·유저 정지·게시글 삭제. AsyncSession.

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.admin.schema import ReportedPostAuthorInfo, ReportedPostItem
from app.auth.service import AuthService
from app.comments.model import CommentsModel
from app.common import UserStatus
from app.common.enums import TargetType
from app.common.exceptions import (
    CommentNotFoundException,
    ConcurrentUpdateException,
    PostNotFoundException,
    UserNotFoundException,
    UserWithdrawnException,
)
from app.posts.repository import PostsModel
from app.reports.model import ReportsModel
from app.users.model import UsersModel

CONTENT_PREVIEW_LEN = 80  # 게시글/댓글 내용 미리보기 글자 수


def _author_from_user(user) -> tuple[ReportedPostAuthorInfo | None, str | None]:
    if not user:
        return None, None
    status = getattr(user, "status", None)
    author = ReportedPostAuthorInfo(
        id=user.id,
        nickname=user.nickname,
        profile_image_url=getattr(user, "profile_image_url", None)
        or (user.profile_image.file_url if getattr(user, "profile_image", None) else None),
        status=status,
    )
    return author, status


class AdminService:
    @classmethod
    async def get_reported_posts(
        cls,
        page: int,
        size: int,
        db: AsyncSession,
    ) -> tuple[list[ReportedPostItem], int]:
        async with db.begin():
            # 각각 최대 500건씩 조회 후 병합·정렬·페이지 슬라이스
            fetch_size = min(500, max(size * 2, (page) * size))
            posts, total_posts = await PostsModel.get_reported_posts(page=1, size=fetch_size, db=db)
            comments, total_comments = await CommentsModel.get_reported_comments(
                page=1, size=fetch_size, db=db
            )
            post_ids = [p.id for p in posts]
            comment_ids = [c.id for c in comments]
            (
                last_at_by_post,
                last_at_by_comment,
                reasons_by_post,
                reasons_by_comment,
            ) = await asyncio.gather(
                ReportsModel.bulk_max_created_at_by_target_ids(TargetType.POST, post_ids, db=db),
                ReportsModel.bulk_max_created_at_by_target_ids(
                    TargetType.COMMENT, comment_ids, db=db
                ),
                ReportsModel.bulk_reasons_ordered_by_target_ids(TargetType.POST, post_ids, db=db),
                ReportsModel.bulk_reasons_ordered_by_target_ids(
                    TargetType.COMMENT, comment_ids, db=db
                ),
            )
            post_items: list[ReportedPostItem] = []
            for p in posts:
                author, author_status = _author_from_user(p.user)
                content_preview = (p.content or "")[:CONTENT_PREVIEW_LEN]
                if len(p.content or "") > CONTENT_PREVIEW_LEN:
                    content_preview += "…"
                post_items.append(
                    ReportedPostItem(
                        target_type="POST",
                        id=p.id,
                        post_id=p.id,
                        title=p.title or "",
                        content_preview=content_preview,
                        user_id=p.user_id,
                        author=author,
                        author_status=author_status,
                        report_count=p.report_count,
                        report_reasons=reasons_by_post.get(p.id, []),
                        is_blinded=p.is_blinded,
                        created_at=p.created_at,
                        last_reported_at=last_at_by_post.get(p.id),
                    )
                )
            title_post_ids = list({c.post_id for c in comments})
            titles_map = await PostsModel.get_titles_by_ids(title_post_ids, db=db)
            comment_items: list[ReportedPostItem] = []
            for c in comments:
                author, author_status = _author_from_user(c.author)
                content_preview = (c.content or "")[:CONTENT_PREVIEW_LEN]
                if len(c.content or "") > CONTENT_PREVIEW_LEN:
                    content_preview += "…"
                comment_items.append(
                    ReportedPostItem(
                        target_type="COMMENT",
                        id=c.id,
                        post_id=c.post_id,
                        title=titles_map.get(c.post_id, ""),
                        content_preview=content_preview,
                        user_id=c.author_id,
                        author=author,
                        author_status=author_status,
                        report_count=c.report_count,
                        report_reasons=reasons_by_comment.get(c.id, []),
                        is_blinded=c.is_blinded,
                        created_at=c.created_at,
                        last_reported_at=last_at_by_comment.get(c.id),
                    )
                )
            merged = post_items + comment_items
            merged.sort(
                key=lambda x: x.last_reported_at or x.created_at,
                reverse=True,
            )
            total = total_posts + total_comments
            start = (page - 1) * size
            items = merged[start : start + size]
            return items, total

    @classmethod
    async def unblind_post(cls, post_id: str, db: AsyncSession) -> None:
        async with db.begin():
            try:
                ok = await PostsModel.unblind_post(post_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e
        if not ok:
            raise PostNotFoundException()

    @classmethod
    async def reset_post_reports(cls, post_id: str, db: AsyncSession) -> None:
        async with db.begin():
            await ReportsModel.delete_by_post_id(post_id, db=db)
            await db.flush()  # delete 반영 후 reset_reports 실행해 재신고 시 목록 노출 보장
            try:
                ok = await PostsModel.reset_reports(post_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e
        if not ok:
            raise PostNotFoundException()

    @classmethod
    async def suspend_user(cls, user_id: str, db: AsyncSession, redis: Any | None = None) -> None:
        async with db.begin():
            user = await UsersModel.get_user_by_id_including_deleted(user_id, db=db)
            if not user:
                raise UserNotFoundException()
            if getattr(user, "deleted_at", None) is not None or UserStatus.is_withdrawn_value(
                getattr(user, "status", None)
            ):
                raise UserWithdrawnException()
            await UsersModel.update_user(user_id, db=db, status=UserStatus.SUSPENDED.value)
        await AuthService.invalidate_user_status_cache(redis, user_id)

    @classmethod
    async def activate_user(cls, user_id: str, db: AsyncSession, redis: Any | None = None) -> None:
        async with db.begin():
            user = await UsersModel.get_user_by_id_including_deleted(user_id, db=db)
            if not user:
                raise UserNotFoundException()
            if getattr(user, "deleted_at", None) is not None or UserStatus.is_withdrawn_value(
                getattr(user, "status", None)
            ):
                raise UserWithdrawnException()
            await UsersModel.update_user(user_id, db=db, status=UserStatus.ACTIVE.value)
        await AuthService.invalidate_user_status_cache(redis, user_id)

    @classmethod
    async def blind_post(cls, post_id: str, db: AsyncSession) -> None:
        async with db.begin():
            try:
                ok = await PostsModel.set_blinded(post_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e
        if not ok:
            raise PostNotFoundException()

    @classmethod
    async def delete_post(cls, post_id: str, db: AsyncSession) -> None:
        # NOTE: AsyncSessionLocal(autobegin=False)이므로, 모든 DB I/O는 명시적 트랜잭션 내부에서 수행.
        #       또한 삭제는 단일 트랜잭션에서 원자적으로 처리(연관 댓글/좋아요/이미지 정리 포함).
        async with db.begin():
            success, _image_ids = await PostsModel.delete_post(post_id, db=db)
            if not success:
                raise PostNotFoundException()

    @classmethod
    async def unblind_comment(cls, comment_id: str, db: AsyncSession) -> None:
        async with db.begin():
            ok = await CommentsModel.unblind_comment(comment_id, db=db)
        if not ok:
            raise CommentNotFoundException()

    @classmethod
    async def blind_comment(cls, comment_id: str, db: AsyncSession) -> None:
        async with db.begin():
            ok = await CommentsModel.set_blinded(comment_id, db=db)
        if not ok:
            raise CommentNotFoundException()

    @classmethod
    async def reset_comment_reports(cls, comment_id: str, db: AsyncSession) -> None:
        async with db.begin():
            await ReportsModel.delete_by_comment_id(comment_id, db=db)
            await db.flush()
            ok = await CommentsModel.reset_reports(comment_id, db=db)
        if not ok:
            raise CommentNotFoundException()

    @classmethod
    async def delete_comment(cls, post_id: str, comment_id: str, db: AsyncSession) -> None:
        async with db.begin():
            # 삭제는 멱등이 아니므로, 먼저 대상 존재 확인 후 삭제/카운트 감소를 같은 트랜잭션에서 처리.
            if await CommentsModel.get_comment_by_id(comment_id, db=db) is None:
                raise CommentNotFoundException()
            deleted = await CommentsModel.delete_comment(post_id, comment_id, db=db)
            if not deleted:
                raise CommentNotFoundException()
            try:
                await PostsModel.decrement_comment_count(post_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e
