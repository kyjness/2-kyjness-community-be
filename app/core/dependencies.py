# app/core/dependencies.py
"""인증·권한 공통 로직 (Route에서 Depends로 사용)."""

from typing import Optional, NamedTuple

from fastapi import Cookie, Depends, Path, Query
from pydantic import ValidationError

from app.auth.model import AuthModel
from app.users.schema import UserAvailabilityQuery
from app.core.codes import ApiCode
from app.core.response import raise_http_error


# -----------------------------------------------------------------------------
# Auth: 세션·현재 사용자
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# Users: 가용성 조회 쿼리
# -----------------------------------------------------------------------------


def parse_availability_query(
    email: Optional[str] = Query(None, description="이메일"),
    nickname: Optional[str] = Query(None, description="닉네임"),
) -> UserAvailabilityQuery:
    """이메일·닉네임 가용 여부 쿼리 파싱. 최소 하나 필수."""
    try:
        return UserAvailabilityQuery(email=email, nickname=nickname)
    except ValidationError:
        raise_http_error(400, ApiCode.INVALID_REQUEST)


# -----------------------------------------------------------------------------
# Posts: 게시글 작성자 권한
# -----------------------------------------------------------------------------


def require_post_author(
    post_id: int = Path(..., description="게시글 ID"),
    current_id: int = Depends(get_current_user),
) -> int:
    """게시글 작성자만 통과. 없으면 404, 타인이면 403. post_id는 경로에서 주입."""
    from app.posts.model import PostsModel

    found = PostsModel.find_post_by_id(post_id)
    if not found:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    post_row = found[0]
    if post_row["user_id"] != current_id:
        raise_http_error(403, ApiCode.FORBIDDEN)
    return post_id


# -----------------------------------------------------------------------------
# Comments: 댓글 작성자 권한
# -----------------------------------------------------------------------------


class CommentAuthorContext(NamedTuple):
    """require_comment_author 통과 시 반환. get_current_user 중복 호출 방지용."""
    user_id: int
    comment_id: int


def require_comment_author(
    post_id: int = Path(..., description="게시글 ID"),
    comment_id: int = Path(..., description="댓글 ID"),
    user_id: int = Depends(get_current_user),
) -> CommentAuthorContext:
    """댓글 작성자만 통과. user_id는 Depends(get_current_user)로 한 번만 주입."""
    from app.comments.model import CommentsModel
    from app.posts.model import PostsModel

    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    comment = CommentsModel.find_comment_by_id(comment_id)
    if not comment:
        raise_http_error(404, ApiCode.COMMENT_NOT_FOUND)
    if comment["post_id"] != post_id:
        raise_http_error(400, ApiCode.INVALID_POSTID_FORMAT)
    if comment["author_id"] != user_id:
        raise_http_error(403, ApiCode.FORBIDDEN)
    return CommentAuthorContext(user_id=user_id, comment_id=comment_id)
