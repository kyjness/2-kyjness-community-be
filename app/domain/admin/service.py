# 관리자 전용: 신고 게시글 목록·블라인드 해제·유저 정지·게시글 삭제. AsyncSession.

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schema import ReportedPostAuthorInfo, ReportedPostItem
from app.common import UserStatus
from app.common.exceptions import PostNotFoundException, UserNotFoundException
from app.posts.model import PostsModel
from app.posts.service import PostService
from app.users.model import UsersModel


class AdminService:
    @classmethod
    async def get_reported_posts(
        cls,
        page: int,
        size: int,
        db: AsyncSession,
    ) -> tuple[list[ReportedPostItem], int]:
        posts, total = await PostsModel.get_reported_posts(page=page, size=size, db=db)
        items: list[ReportedPostItem] = []
        for p in posts:
            author = None
            if p.user:
                author = ReportedPostAuthorInfo(
                    id=p.user.id,
                    nickname=p.user.nickname,
                    profile_image_url=getattr(p.user, "profile_image_url", None)
                    or (p.user.profile_image.file_url if p.user.profile_image else None),
                )
            items.append(
                ReportedPostItem(
                    id=p.id,
                    title=p.title,
                    user_id=p.user_id,
                    author=author,
                    report_count=p.report_count,
                    is_blinded=p.is_blinded,
                    created_at=p.created_at,
                )
            )
        return items, total

    @classmethod
    async def unblind_post(cls, post_id: int, db: AsyncSession) -> None:
        async with db.begin():
            ok = await PostsModel.unblind_post(post_id, db=db)
        if not ok:
            raise PostNotFoundException()

    @classmethod
    async def suspend_user(cls, user_id: int, db: AsyncSession) -> None:
        async with db.begin():
            user = await UsersModel.get_user_by_id(user_id, db=db)
            if not user:
                raise UserNotFoundException()
            await UsersModel.update_user(user_id, db=db, status=UserStatus.SUSPENDED.value)

    @classmethod
    async def delete_post(cls, post_id: int, db: AsyncSession) -> None:
        if await PostsModel.get_post_author_id(post_id, db=db) is None:
            raise PostNotFoundException()
        await PostService.delete_post(post_id, db=db)
