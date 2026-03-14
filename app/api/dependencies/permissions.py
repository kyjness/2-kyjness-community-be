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
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
) -> int:
    async with db.begin():
        author_id = await PostsModel.get_post_author_id(post_id, db=db)
    if author_id is None:
        raise PostNotFoundException()
    if author_id != user.id:
        raise ForbiddenException()
    return post_id


class CommentAuthorContext(NamedTuple):
    post_id: int
    user_id: int
    comment_id: int


async def require_comment_author(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    comment_id: int = Path(..., ge=1, description="댓글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
) -> CommentAuthorContext:
    async with db.begin():
        author_id = await PostsModel.get_post_author_id(post_id, db=db)
        comment = await CommentsModel.get_comment_by_id(comment_id, db=db)
        if author_id is None:
            raise PostNotFoundException()
        if not comment:
            raise CommentNotFoundException()
        if comment.post_id != post_id:
            raise InvalidPostIdFormatException()
        if comment.author_id != user.id:
            raise ForbiddenException()
        return CommentAuthorContext(post_id=post_id, user_id=user.id, comment_id=comment_id)


async def require_comment_author_for_delete(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    comment_id: int = Path(..., ge=1, description="댓글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_slave_db),
) -> CommentAuthorContext:
    """삭제 시 이미 삭제된 댓글도 작성자로 인정해 204 멱등 응답."""
    async with db.begin():
        author_id = await PostsModel.get_post_author_id(post_id, db=db)
        comment = await CommentsModel.get_comment_by_id(comment_id, db=db, include_deleted=True)
        if author_id is None:
            raise PostNotFoundException()
        if not comment:
            raise CommentNotFoundException()
        if comment.post_id != post_id:
            raise InvalidPostIdFormatException()
        if comment.author_id != user.id:
            raise ForbiddenException()
        return CommentAuthorContext(post_id=post_id, user_id=user.id, comment_id=comment_id)
