# 게시글 비즈니스 로직. 생성·수정·삭제·피드·상세·좋아요·조회수.
import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common import ApiCode, raise_http_error, success_response
from app.api.dependencies import CurrentUser
from app.media.model import MediaModel
from app.posts.model import PostsModel, PostLikesModel
from app.posts.schema import PostCreateRequest, PostResponse, PostUpdateRequest

logger = logging.getLogger(__name__)


def create_post(
    user: CurrentUser,
    data: PostCreateRequest,
    db: Session,
) -> dict:
    try:
        if data.image_ids:
            images = MediaModel.get_images_by_ids(data.image_ids, db=db)
            if set(i.id for i in images) != set(data.image_ids):
                raise_http_error(400, ApiCode.INVALID_REQUEST)
        post_id = PostsModel.create_post(user.id, data.title, data.content, data.image_ids, db=db)
        return success_response(ApiCode.POST_UPLOADED, {"postId": post_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("게시글 작성 실패 user_id=%s: %s", user.id, e)
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)


def get_posts(
    page: int = 1,
    size: int = 10,
    *,
    db: Session,
) -> dict:
    posts, has_more = PostsModel.get_all_posts(page, size, db=db)
    result = []
    for post in posts:
        if not post.user:
            continue
        result.append(PostResponse.model_validate(post).model_dump(by_alias=True))
    return {"code": ApiCode.POSTS_RETRIEVED.value, "data": result, "hasMore": has_more}


def record_post_view(post_id: int, db: Session) -> None:
    post = PostsModel.get_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    PostsModel.increment_view_count(post_id, db=db)


def get_post(post_id: int, db: Session) -> dict:
    post = PostsModel.get_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if not post.user:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    return success_response(ApiCode.POST_RETRIEVED, PostResponse.model_validate(post))


def update_post(
    post_id: int,
    data: PostUpdateRequest,
    db: Session,
) -> dict:
    post = PostsModel.get_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    if data.image_ids is not None:
        images = MediaModel.get_images_by_ids(data.image_ids, db=db)
        if set(i.id for i in images) != set(data.image_ids):
            raise_http_error(400, ApiCode.INVALID_REQUEST)
    PostsModel.update_post(post_id, title=data.title, content=data.content, image_ids=data.image_ids, db=db)
    return success_response(ApiCode.POST_UPDATED)


def delete_post(post_id: int, db: Session) -> None:
    """복수 모델 조작 원자성: 실패 시 전체 롤백. 상세는 docs/architecture.md 참고."""
    with db.begin():
        if not PostsModel.delete_post(post_id, db=db):
            raise_http_error(404, ApiCode.POST_NOT_FOUND)


def add_like(post_id: int, user: CurrentUser, db: Session) -> tuple[dict, int]:
    post = PostsModel.get_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    PostLikesModel.add_like(post_id, user.id, db=db)
    like_count = PostsModel.increment_like_count(post_id, db=db)
    return success_response(ApiCode.LIKE_SUCCESS, {"likeCount": like_count}), 201


def delete_like(
    post_id: int,
    user: CurrentUser,
    db: Session,
) -> None:
    post = PostsModel.get_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    deleted = PostLikesModel.delete_like(post_id, user.id, db=db)
    if deleted:
        PostsModel.decrement_like_count(post_id, db=db)
