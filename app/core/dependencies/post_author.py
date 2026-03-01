# 게시글 작성자 검증. require_post_author (수정/삭제 시 본인 여부).
from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.common import ApiCode, raise_http_error
from app.db import get_db
from app.core.dependencies.current_user import CurrentUser, get_current_user
from app.posts.model import PostsModel


def require_post_author(
    post_id: int = Path(..., ge=1, description="게시글 ID"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    author_id = PostsModel.get_post_author_id(post_id, db=db)
    if author_id is None:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if author_id != user.id:
        raise_http_error(403, ApiCode.FORBIDDEN)
    return post_id
