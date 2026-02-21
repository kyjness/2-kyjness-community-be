# app/posts/posts_controller.py
"""게시글 비즈니스 로직. 권한(작성자)은 Route(require_post_author), 검증·응답은 core 사용."""

import logging
from typing import Optional, List

from fastapi import HTTPException

from app.posts.posts_model import PostsModel, PostLikesModel
from app.posts.posts_schema import PostCreateRequest, PostUpdateRequest, PostResponse, AuthorInfo, FileInfo
from app.users.users_model import UsersModel
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error
from app.media.media_model import MediaModel

logger = logging.getLogger(__name__)


def _validate_image_ids(image_ids: Optional[List[int]]) -> None:
    """imageIds가 images 테이블에 존재하는지 검사. 없으면 400."""
    if not image_ids:
        return
    for iid in image_ids:
        if MediaModel.get_url_by_id(iid) is None:
            raise_http_error(400, ApiCode.INVALID_REQUEST)


def create_post(user_id: int, data: PostCreateRequest):
    try:
        _validate_image_ids(data.imageIds)
        post = PostsModel.create_post(user_id, data.title, data.content, data.imageIds)
        return success_response(ApiCode.POST_UPLOADED, {"postId": post["postId"]})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("게시글 작성 실패 user_id=%s: %s", user_id, e)
        raise


def _build_post_response_item(post: dict, author: dict) -> dict:
    """단일 게시글 + 작성자 정보를 API 응답 형식으로 구성."""
    item = PostResponse(
        postId=post["postId"],
        title=post["title"],
        content=post["content"],
        hits=post["hits"],
        likeCount=post["likeCount"],
        commentCount=post["commentCount"],
        author=AuthorInfo(
            userId=author["userId"],
            nickname=author["nickname"],
            profileImageUrl=author.get("profileImageUrl", ""),
        ),
        files=[FileInfo(**f) for f in post.get("files", [])],
        createdAt=post["createdAt"],
    )
    return item.model_dump()


def get_posts(page: int = 1, size: int = 10):
    """무한 스크롤용 게시글 목록. data, hasMore 반환."""
    posts_raw, has_more = PostsModel.get_all_posts(page, size)
    result = []
    for post in posts_raw:
        author = UsersModel.find_user_by_id(post["authorId"])
        if author:
            result.append(_build_post_response_item(post, author))
    return {"code": ApiCode.POSTS_RETRIEVED.value, "data": result, "hasMore": has_more}


def record_view(post_id: int) -> None:
    """조회수 1 증가. 페이지 진입 시 전용. 게시글 없으면 404."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    PostsModel.increment_hits(post_id)


def get_post(post_id: int):
    """게시글 상세 조회. 조회수는 POST /view에서 별도 처리."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    author = UsersModel.find_user_by_id(post["authorId"])
    if not author:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    data = _build_post_response_item(post, author)
    return success_response(ApiCode.POST_RETRIEVED, data)


def update_post(post_id: int, user_id: int, data: PostUpdateRequest):
    """게시글 수정. 작성자 검사는 Route(require_post_author)에서 수행."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if data.imageIds is not None:
        _validate_image_ids(data.imageIds)
    PostsModel.update_post(post_id, title=data.title, content=data.content, image_ids=data.imageIds)
    return success_response(ApiCode.POST_UPDATED)


def delete_post(post_id: int, user_id: int):
    """게시글 삭제. 작성자 검사는 Route(require_post_author)에서 수행. 성공 시 반환 없음(route에서 204 반환)."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    PostsModel.delete_post(post_id)


def create_like(post_id: int, user_id: int):
    """게시글 좋아요 추가. 로그인 사용자만 가능."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    liker_key = PostLikesModel._liker_key_user(user_id)
    if PostLikesModel.has_liked(post_id, liker_key):
        current = post.get("likeCount", 0) or 0
        return success_response(ApiCode.ALREADY_LIKED, {"likeCount": current})
    like = PostLikesModel.create_like(post_id, liker_key, user_id=user_id)
    if not like:
        raise_http_error(409, ApiCode.CONFLICT)
    like_count = PostsModel.increment_like_count(post_id)
    return success_response(ApiCode.POSTLIKE_UPLOADED, {"likeCount": like_count})


def delete_like(post_id: int, user_id: int):
    """게시글 좋아요 취소. 로그인 사용자만 가능."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    liker_key = PostLikesModel._liker_key_user(user_id)
    if not PostLikesModel.has_liked(post_id, liker_key):
        raise_http_error(404, ApiCode.LIKE_NOT_FOUND)
    PostLikesModel.delete_like(post_id, liker_key)
    like_count = PostsModel.decrement_like_count(post_id)
    return success_response(ApiCode.LIKE_DELETED, {"likeCount": like_count})
