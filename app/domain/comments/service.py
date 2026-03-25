# 댓글 비즈니스 로직. Full-Async. 생성/삭제 시 게시글 comment_count 조정은 서비스에서 조율.
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.comments.model import CommentLikesModel, CommentsModel
from app.comments.schema import (
    CommentIdData,
    CommentResponse,
    CommentsPageData,
    CommentUpsertRequest,
)
from app.common.exceptions import (
    CommentNotFoundException,
    ConcurrentUpdateException,
    PostNotFoundException,
)


async def _increment_post_comment_count(post_id: int, db: AsyncSession) -> None:
    from app.posts.model import PostsModel

    await PostsModel.increment_comment_count(post_id, db=db)


async def _decrement_post_comment_count(post_id: int, db: AsyncSession) -> None:
    from app.posts.model import PostsModel

    await PostsModel.decrement_comment_count(post_id, db=db)


async def _ensure_post_visible(
    post_id: int,
    db: AsyncSession,
    current_user_id: int | None = None,
) -> None:
    from app.posts.model import PostsModel

    if await PostsModel.get_post_by_id(post_id, db=db, current_user_id=current_user_id) is None:
        raise PostNotFoundException()


def _comment_to_response(
    c, liked_ids: set, deleted_content_placeholder: str = "삭제된 댓글입니다."
):
    """AsyncSession에서는 lazy load 금지이므로, c.replies에 접근하지 않고 필드만 넣어 응답 생성."""
    is_edited = c.updated_at > c.created_at if (c.updated_at and c.created_at) else False
    is_deleted = c.deleted_at is not None
    content = (c.content if not is_deleted else deleted_content_placeholder) or ""
    return CommentResponse(
        id=c.id,
        content=content,
        author=c.author,
        created_at=c.created_at,
        updated_at=c.updated_at,
        post_id=c.post_id,
        parent_id=c.parent_id,
        like_count=c.like_count,
        is_liked=c.id in liked_ids,
        is_edited=is_edited,
        is_deleted=is_deleted,
        replies=[],
    )


def _build_comment_tree(
    comments: list,
    liked_ids: set,
    sort: str = "latest",
) -> list[CommentResponse]:
    by_id = {}
    roots: list[CommentResponse] = []
    for c in comments:
        resp = _comment_to_response(c, liked_ids)
        by_id[c.id] = resp
    for c in comments:
        resp = by_id[c.id]
        if c.parent_id is None:
            roots.append(resp)
        else:
            parent = by_id.get(c.parent_id)
            if parent is not None:
                parent.replies.append(resp)
            else:
                roots.append(resp)
    roots = [r for r in roots if not (getattr(r, "is_deleted", False) and len(r.replies) == 0)]
    if sort == "oldest":
        roots.sort(key=lambda r: r.id)
        for r in roots:
            r.replies.sort(key=lambda x: x.id)
    elif sort == "popular":
        roots.sort(key=lambda r: (getattr(r, "like_count", 0), r.id), reverse=True)
        for r in roots:
            r.replies.sort(key=lambda x: (getattr(x, "like_count", 0), x.id), reverse=True)
    else:
        roots.sort(key=lambda r: r.id, reverse=True)
        for r in roots:
            r.replies.sort(key=lambda x: x.id, reverse=True)
    return roots


class CommentService:
    @classmethod
    async def create_comment(
        cls,
        post_id: int,
        user_id: int,
        data: CommentUpsertRequest,
        db: AsyncSession,
    ) -> CommentIdData:
        async with db.begin():
            await _ensure_post_visible(post_id, db=db, current_user_id=user_id)
            parent_id = getattr(data, "parent_id", None)
            if parent_id is not None:
                parent = await CommentsModel.get_comment_by_id(parent_id, db=db)
                if not parent or parent.post_id != post_id or parent.deleted_at is not None:
                    raise CommentNotFoundException()
                if parent.parent_id is not None:
                    raise CommentNotFoundException()
            comment = await CommentsModel.create_comment(
                post_id, user_id, data.content, db=db, parent_id=parent_id
            )
            try:
                await _increment_post_comment_count(post_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e
            comment_id = comment.id
        return CommentIdData(id=comment_id)

    @classmethod
    async def get_comments(
        cls,
        post_id: int,
        page: int,
        size: int,
        db: AsyncSession,
        sort: str | None = None,
        current_user_id: int | None = None,
    ) -> CommentsPageData:
        async with db.begin():
            from app.posts.model import PostsModel

            post = await PostsModel.get_post_by_id(post_id, db=db, current_user_id=current_user_id)
            if not post:
                raise PostNotFoundException()
            comments = await CommentsModel.get_comments_by_post_id(
                post_id,
                page=page,
                size=size,
                db=db,
                fetch_all_for_tree=True,
                current_user_id=current_user_id,
            )
            total_count = post.comment_count
            comment_ids = [c.id for c in comments]
            liked_ids = (
                await CommentLikesModel.get_liked_comment_ids_for_user(
                    current_user_id, comment_ids, db=db
                )
                if current_user_id is not None
                else set()
            )
            result = _build_comment_tree(comments, liked_ids, sort=sort or "latest")
        return CommentsPageData(
            items=result,
            total_count=total_count,
            total_pages=1,
            current_page=1,
        )

    @classmethod
    async def update_comment(
        cls,
        post_id: int,
        comment_id: int,
        data: CommentUpsertRequest,
        db: AsyncSession,
    ) -> None:
        async with db.begin():
            affected = await CommentsModel.update_comment(post_id, comment_id, data.content, db=db)
            if affected == 0:
                raise CommentNotFoundException()

    @classmethod
    async def delete_comment(cls, post_id: int, comment_id: int, db: AsyncSession) -> None:
        async with db.begin():
            comment = await CommentsModel.get_comment_by_id(comment_id, db=db, include_deleted=True)
            if comment is None or comment.post_id != post_id:
                raise CommentNotFoundException()
            if comment.deleted_at is not None:
                return  # 이미 삭제됨 → 204 (멱등)
            deleted = await CommentsModel.delete_comment(post_id, comment_id, db=db)
            if not deleted:
                raise CommentNotFoundException()
            try:
                await _decrement_post_comment_count(post_id, db=db)
            except StaleDataError as e:
                raise ConcurrentUpdateException() from e
