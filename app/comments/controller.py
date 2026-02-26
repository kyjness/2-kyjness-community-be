import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.comments.model import CommentsModel
from app.comments.schema import CommentResponse, CommentUpsertRequest
from app.common import ApiCode, raise_http_error, success_response
from app.core.dependencies import CurrentUser
from app.posts.model import PostsModel

logger = logging.getLogger(__name__)


def create_comment(post_id: int, user: CurrentUser, data: CommentUpsertRequest, db: Session) -> dict:
    post = PostsModel.find_post_by_id(post_id, db=db)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    try:
        row = CommentsModel.create_comment(post_id, user.id, data.content, db=db)
        PostsModel.increment_comment_count(post_id, db=db)
        return success_response(ApiCode.COMMENT_UPLOADED, {"commentId": row["id"]})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("댓글 저장 실패 post_id=%s user_id=%s: %s", post_id, user.id, e)
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)


def get_comments(post_id: int, page: int, size: int, db: Session) -> dict:
    if PostsModel.find_post_by_id(post_id, db=db) is None:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    rows = CommentsModel.get_comments_by_post_id(post_id, page, size, db=db)
    total_count = CommentsModel.get_comment_count_by_post_id(post_id, db=db)
    total_pages = max(1, (total_count + size - 1) // size) if total_count > 0 else 1

    result = []
    for row in rows:
        payload = {
            "id": row["id"],
            "post_id": row["post_id"],
            "author_id": row["author_id"],
            "content": row["content"],
            "created_at": row["created_at"],
            "author": {
                "id": row["author_user_id"],
                "nickname": row["author_nickname"],
                "profile_image_url": row.get("author_profile_image_url"),
            },
            "post_id": post_id,
        }
        result.append(CommentResponse.model_validate(payload).model_dump(by_alias=True))
    payload = {"list": result, "totalCount": total_count, "totalPages": total_pages, "currentPage": page}
    return success_response(ApiCode.COMMENTS_RETRIEVED, payload)


def update_comment(post_id: int, comment_id: int, data: CommentUpsertRequest, db: Session) -> dict:
    affected = CommentsModel.update_comment(post_id, comment_id, data.content, db=db)
    if affected == 0:
        raise_http_error(404, ApiCode.COMMENT_NOT_FOUND)
    return success_response(ApiCode.COMMENT_UPDATED)


def withdraw_comment(post_id: int, comment_id: int, db: Session) -> None:
    withdrawn = CommentsModel.withdraw_comment(post_id, comment_id, db=db)
    if not withdrawn:
        raise_http_error(404, ApiCode.COMMENT_NOT_FOUND)
    PostsModel.decrement_comment_count(post_id, db=db)
