import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common import ApiCode, raise_http_error, success_response
from app.core.dependencies import CurrentUser
from app.media.model import MediaModel
from app.posts.mapper import to_post_response
from app.posts.model import PostsModel, PostLikesModel
from app.posts.schema import PostCreateRequest, PostUpdateRequest

logger = logging.getLogger(__name__)


def create_post(user: CurrentUser, data: PostCreateRequest, db: Session) -> dict:
    try:
        if data.image_ids:
            for iid in data.image_ids:
                if MediaModel.get_url_by_id(iid, db=db) is None:
                    raise_http_error(400, ApiCode.INVALID_REQUEST)
        post_id = PostsModel.create_post(user.id, data.title, data.content, data.image_ids, db=db)
        return success_response(ApiCode.POST_UPLOADED, {"postId": post_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("게시글 작성 실패 user_id=%s: %s", user.id, e)
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)


def get_posts(page: int = 1, size: int = 10, *, db: Session) -> dict:
    posts, has_more = PostsModel.get_all_posts(page, size, db=db)
    result = []
    for post in posts:
        if not post.user:
            continue
        result.append(to_post_response(post))
    return {"code": ApiCode.POSTS_RETRIEVED.value, "data": result, "hasMore": has_more}


def record_post_view(post_id: int, db: Session) -> None:
    post = PostsModel.find_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    PostsModel.increment_view_count(post_id, db=db)


def get_post(post_id: int, db: Session) -> dict:
    post = PostsModel.find_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if not post.user:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    return success_response(ApiCode.POST_RETRIEVED, to_post_response(post))


def update_post(post_id: int, data: PostUpdateRequest, db: Session) -> dict:
    post = PostsModel.find_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if data.image_ids is not None:
        for iid in data.image_ids:
            if MediaModel.get_url_by_id(iid, db=db) is None:
                raise_http_error(400, ApiCode.INVALID_REQUEST)
    PostsModel.update_post(post_id, title=data.title, content=data.content, image_ids=data.image_ids, db=db)
    return success_response(ApiCode.POST_UPDATED)


def withdraw_post(post_id: int, db: Session) -> None:
    if not PostsModel.withdraw_post(post_id, db=db):
        raise_http_error(404, ApiCode.POST_NOT_FOUND)


def add_like(post_id: int, user: CurrentUser, db: Session) -> tuple[dict, int]:
    post = PostsModel.find_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    added = PostLikesModel.add_like(post_id, user.id, db=db)
    if added is None:
        like_count = PostsModel.get_like_count(post_id, db=db)
        return success_response(ApiCode.ALREADY_LIKED, {"likeCount": like_count}), 200
    like_count = PostsModel.increment_like_count(post_id, db=db)
    return success_response(ApiCode.POSTLIKE_UPLOADED, {"likeCount": like_count}), 201


def remove_like(post_id: int, user: CurrentUser, db: Session) -> dict:
    post = PostsModel.find_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if not PostLikesModel.remove_like(post_id, user.id, db=db):
        raise_http_error(404, ApiCode.LIKE_NOT_FOUND)
    like_count = PostsModel.decrement_like_count(post_id, db=db)
    return success_response(ApiCode.LIKE_DELETED, {"likeCount": like_count})
