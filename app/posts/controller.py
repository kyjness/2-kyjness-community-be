# app/posts/controller.py
"""게시글 비즈니스 로직."""

import logging

from fastapi import HTTPException

from app.posts.model import PostsModel, PostLikesModel
from app.posts.schema import PostCreateRequest, PostUpdateRequest, PostResponse
from app.users.model import UsersModel
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error
from app.media.model import MediaModel

logger = logging.getLogger(__name__)


def create_post(user_id: int, data: PostCreateRequest):
    try:
        if data.imageIds:
            for iid in data.imageIds:
                if MediaModel.get_url_by_id(iid) is None:
                    raise_http_error(400, ApiCode.INVALID_REQUEST)
        post_id = PostsModel.create_post(user_id, data.title, data.content, data.imageIds)
        return success_response(ApiCode.POST_UPLOADED, {"postId": post_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("게시글 작성 실패 user_id=%s: %s", user_id, e)
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)


def get_posts(page: int = 1, size: int = 10):
    posts_with_files, has_more = PostsModel.get_all_posts(page, size)
    result = []
    for post_row, file_rows in posts_with_files:
        author = UsersModel.find_user_by_id(post_row["user_id"])
        if author:
            result.append(
                PostResponse.from_rows(post_row, file_rows, author).model_dump(by_alias=True)
            )
    return {"code": ApiCode.POSTS_RETRIEVED.value, "data": result, "hasMore": has_more}


def record_post_view(post_id: int) -> None:
    if PostsModel.find_post_by_id(post_id) is None:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    PostsModel.increment_hits(post_id)


def get_post(post_id: int):
    found = PostsModel.find_post_by_id(post_id)
    if not found:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    post_row, file_rows = found
    author = UsersModel.find_user_by_id(post_row["user_id"])
    if not author:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    data = PostResponse.from_rows(post_row, file_rows, author).model_dump(by_alias=True)
    return success_response(ApiCode.POST_RETRIEVED, data)


def update_post(post_id: int, data: PostUpdateRequest):
    if PostsModel.find_post_by_id(post_id) is None:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if data.imageIds is not None:
        for iid in data.imageIds:
            if MediaModel.get_url_by_id(iid) is None:
                raise_http_error(400, ApiCode.INVALID_REQUEST)
    PostsModel.update_post(post_id, title=data.title, content=data.content, image_ids=data.imageIds)
    return success_response(ApiCode.POST_UPDATED)


def withdraw_post(post_id: int):
    if not PostsModel.withdraw_post(post_id):
        raise_http_error(404, ApiCode.POST_NOT_FOUND)


def create_like(post_id: int, user_id: int) -> tuple[dict, int]:
    """(응답 dict, HTTP status_code) 반환. 이미 좋아요 시 200, 새로 추가 시 201."""
    found = PostsModel.find_post_by_id(post_id)
    if not found:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    post_row, _ = found
    liker_key = PostLikesModel._liker_key_user(user_id)
    if PostLikesModel.has_liked(post_id, liker_key):
        current = post_row.get("like_count", 0) or 0
        return success_response(ApiCode.ALREADY_LIKED, {"likeCount": current}), 200
    like = PostLikesModel.create_like(post_id, liker_key, user_id=user_id)
    if not like:
        raise_http_error(409, ApiCode.CONFLICT)
    like_count = PostsModel.increment_like_count(post_id)
    return success_response(ApiCode.POSTLIKE_UPLOADED, {"likeCount": like_count}), 201


def delete_like(post_id: int, user_id: int):
    if PostsModel.find_post_by_id(post_id) is None:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    liker_key = PostLikesModel._liker_key_user(user_id)
    if not PostLikesModel.has_liked(post_id, liker_key):
        raise_http_error(404, ApiCode.LIKE_NOT_FOUND)
    PostLikesModel.delete_like(post_id, liker_key)
    like_count = PostsModel.decrement_like_count(post_id)
    return success_response(ApiCode.LIKE_DELETED, {"likeCount": like_count})
