# app/posts/posts_controller.py
"""게시글 비즈니스 로직. 권한(작성자)은 Route(require_post_author), 검증·응답은 core 사용."""

import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

from app.posts.posts_model import PostsModel, PostLikesModel
from app.posts.posts_schema import PostCreateRequest, PostUpdateRequest, PostResponse, AuthorInfo, FileInfo
from app.auth.auth_model import AuthModel
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error
from app.media.media_model import MediaModel


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
    except Exception as e:
        logger.exception("게시글 작성 실패 user_id=%s: %s", user_id, e)
        raise


def _post_to_response_item(post: dict, author: dict) -> dict:
    """단일 게시글 dict를 PostResponse 스키마로 검증 후 반환."""
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
        author = AuthModel.find_user_by_id(post["authorId"])
        if author:
            result.append(_post_to_response_item(post, author))
    return {"code": ApiCode.POSTS_RETRIEVED.value, "data": result, "hasMore": has_more}


def get_post(post_id: int):
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    PostsModel.increment_hits(post_id)
    author = AuthModel.find_user_by_id(post["authorId"])
    if not author:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    post_with_hits = {**post, "hits": post["hits"] + 1}
    data = _post_to_response_item(post_with_hits, author)
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
    """게시글 좋아요 추가."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if PostLikesModel.has_liked(post_id, user_id):
        raise_http_error(409, ApiCode.CONFLICT)
    like = PostLikesModel.create_like(post_id, user_id)
    if not like:
        raise_http_error(409, ApiCode.CONFLICT)
    PostsModel.increment_like_count(post_id)
    updated_post = PostsModel.find_post_by_id(post_id)
    like_count = updated_post["likeCount"] if updated_post else 0
    return success_response(ApiCode.POSTLIKE_UPLOADED, {"likeCount": like_count})


def delete_like(post_id: int, user_id: int):
    """게시글 좋아요 취소. 응답에 likeCount 포함."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if not PostLikesModel.has_liked(post_id, user_id):
        raise_http_error(404, ApiCode.LIKE_NOT_FOUND)
    PostLikesModel.delete_like(post_id, user_id)
    PostsModel.decrement_like_count(post_id)
    updated_post = PostsModel.find_post_by_id(post_id)
    like_count = updated_post["likeCount"] if updated_post else 0
    return success_response(ApiCode.LIKE_DELETED, {"likeCount": like_count})
