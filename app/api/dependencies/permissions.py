# 권한 의존성. 게시글/댓글 작성자 검증. Full-Async.
from typing import NamedTuple

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.comments.model import CommentsModel
from app.common.exceptions import (
    CommentNotFoundException,
    ForbiddenException,
    InvalidPostIdFormatException,
    PostNotFoundException,
)
from app.posts.model import PostsModel

from .auth import CurrentUser, get_current_user
from .db import get_slave_db


async def require_post_author(
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
) -> str:
    async with db.begin():
        author_id = await PostsModel.get_post_author_id(post_id, db=db)
    if author_id is None:
        raise PostNotFoundException()
    if author_id != user.id:
        raise ForbiddenException()
    return post_id


class CommentAuthorContext(NamedTuple):
    post_id: str
    user_id: str
    comment_id: str


async def require_comment_author(
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    comment_id: str = Path(..., min_length=26, max_length=26, description="댓글 ULID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
) -> CommentAuthorContext:
    async with db.begin():
        row = await CommentsModel.load_comment_author_permission_row(
            post_id,
            comment_id,
            db=db,
            include_deleted_comment=False,
        )
    if row is None:
        raise PostNotFoundException()
    if row.comment_id is None:
        raise CommentNotFoundException()
    if row.comment_post_id != post_id:
        raise InvalidPostIdFormatException()
    if row.comment_author_id != user.id:
        raise ForbiddenException()
    return CommentAuthorContext(post_id=post_id, user_id=user.id, comment_id=comment_id)


async def require_comment_author_for_delete(
    post_id: str = Path(..., min_length=26, max_length=26, description="게시글 ULID"),
    comment_id: str = Path(..., min_length=26, max_length=26, description="댓글 ULID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
) -> CommentAuthorContext:
    """삭제 시 이미 삭제된 댓글도 작성자로 인정해 204 멱등 응답."""
    async with db.begin():
        row = await CommentsModel.load_comment_author_permission_row(
            post_id,
            comment_id,
            db=db,
            include_deleted_comment=True,
        )
    if row is None:
        raise PostNotFoundException()
    if row.comment_id is None:
        raise CommentNotFoundException()
    if row.comment_post_id != post_id:
        raise InvalidPostIdFormatException()
    if row.comment_author_id != user.id:
        raise ForbiddenException()
    return CommentAuthorContext(post_id=post_id, user_id=user.id, comment_id=comment_id)
