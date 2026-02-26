from typing import NamedTuple

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.comments.model import CommentsModel
from app.common import ApiCode, raise_http_error
from app.core.database import get_db
from app.core.dependencies.current_user import CurrentUser, get_current_user
from app.posts.model import PostsModel


class CommentAuthorContext(NamedTuple):
    post_id: int
    user_id: int
    comment_id: int


def require_comment_author(post_id: int = Path(..., ge=1, description="게시글 ID"), comment_id: int = Path(..., ge=1, description="댓글 ID"), user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> CommentAuthorContext:
    if PostsModel.get_post_author_id(post_id, db=db) is None:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    comment = CommentsModel.find_comment_by_id(comment_id, db=db)
    if not comment:
        raise_http_error(404, ApiCode.COMMENT_NOT_FOUND)
    if comment["post_id"] != post_id:
        raise_http_error(400, ApiCode.INVALID_POSTID_FORMAT)
    if comment["author_id"] != user.id:
        raise_http_error(403, ApiCode.FORBIDDEN)
    return CommentAuthorContext(post_id=post_id, user_id=user.id, comment_id=comment_id)
