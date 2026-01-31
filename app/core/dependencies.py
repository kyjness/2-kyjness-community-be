# app/core/dependencies.py
"""인증·권한 공통 로직 (Route에서 Depends로 사용)."""

import logging
from typing import Optional

from fastapi import Cookie, Depends

from app.auth.auth_model import AuthModel
from app.core.response import raise_http_error

logger = logging.getLogger(__name__)


def get_current_user(session_id: Optional[str] = Cookie(None)) -> int:
    """인증된 사용자 ID 반환. 없거나 무효면 401."""
    if not session_id:
        logger.warning("Authentication failed: No session ID provided")
        raise_http_error(401, "UNAUTHORIZED")
    user_id = AuthModel.verify_token(session_id)
    if not user_id:
        logger.warning("Authentication failed: Invalid session ID")
        raise_http_error(401, "UNAUTHORIZED")
    return user_id


def require_same_user(user_id: int, current_id: int = Depends(get_current_user)) -> int:
    """Path user_id와 로그인 사용자가 동일한지 검사. 아니면 403."""
    if current_id != user_id:
        raise_http_error(403, "FORBIDDEN")
    return user_id


def require_post_author(post_id: int, current_id: int = Depends(get_current_user)) -> int:
    """게시글 작성자만 통과. 없으면 404, 타인이면 403."""
    from app.posts.posts_model import PostsModel

    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    if post["authorId"] != current_id:
        raise_http_error(403, "FORBIDDEN")
    return post_id


def require_comment_author(
    post_id: int,
    comment_id: int,
    current_id: int = Depends(get_current_user),
) -> int:
    """댓글 작성자만 통과. 게시글/댓글 없으면 404, 타인이면 403."""
    from app.comments.comments_model import CommentsModel
    from app.posts.posts_model import PostsModel

    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    comment = CommentsModel.find_comment_by_id(comment_id)
    if not comment:
        raise_http_error(404, "COMMENT_NOT_FOUND")
    if comment["postId"] != post_id:
        raise_http_error(400, "INVALID_POSTID_FORMAT")
    if comment["authorId"] != current_id:
        raise_http_error(403, "FORBIDDEN")
    return comment_id
