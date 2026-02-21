# app/core/dependencies.py
"""인증·권한 공통 로직 (Route에서 Depends로 사용). Path 파라미터는 의존성에서 명시적으로 선언."""

from typing import Optional

from fastapi import Cookie, Depends, Path

from app.auth.model import AuthModel
from app.core.codes import ApiCode
from app.core.response import raise_http_error


def get_current_user(session_id: Optional[str] = Cookie(None)) -> int:
    """Cookie의 session_id로 세션 저장소에서 user_id 조회. 없거나 무효면 401 (JWT 아님)."""
    if not session_id:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    user_id = AuthModel.get_user_id_by_session(session_id)
    if not user_id:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    return user_id


def get_current_user_optional(session_id: Optional[str] = Cookie(None)) -> Optional[int]:
    """세션 있으면 user_id 반환, 없거나 무효면 None. 비로그인 업로드 허용용."""
    if not session_id:
        return None
    return AuthModel.get_user_id_by_session(session_id)


def require_post_author(
    post_id: int = Path(..., description="게시글 ID"),
    current_id: int = Depends(get_current_user),
) -> int:
    """게시글 작성자만 통과. 없으면 404, 타인이면 403. post_id는 경로에서 주입."""
    from app.posts.model import PostsModel

    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if post["authorId"] != current_id:
        raise_http_error(403, ApiCode.FORBIDDEN)
    return post_id


def require_comment_author(
    post_id: int = Path(..., description="게시글 ID"),
    comment_id: int = Path(..., description="댓글 ID"),
    current_id: int = Depends(get_current_user),
) -> int:
    """댓글 작성자만 통과. post_id, comment_id는 경로에서 주입."""
    from app.comments.model import CommentsModel
    from app.posts.model import PostsModel

    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    comment = CommentsModel.find_comment_by_id(comment_id)
    if not comment:
        raise_http_error(404, ApiCode.COMMENT_NOT_FOUND)
    if comment["postId"] != post_id:
        raise_http_error(400, ApiCode.INVALID_POSTID_FORMAT)
    if comment["authorId"] != current_id:
        raise_http_error(403, ApiCode.FORBIDDEN)
    return comment_id
