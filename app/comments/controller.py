# app/comments/controller.py

import logging

from fastapi import HTTPException

from app.comments.model import CommentsModel
from app.comments.schema import CommentUpsertRequest, CommentResponse
from app.core.database import get_connection
from app.posts.model import PostsModel
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error

logger = logging.getLogger(__name__)


def create_comment(post_id: int, user_id: int, data: CommentUpsertRequest) -> dict:
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    try:
        # 동일 conn으로 댓글 INSERT + 카운트 갱신 후 한 번만 commit (카운트 정합성)
        with get_connection() as conn:
            row = CommentsModel.create_comment(post_id, user_id, data.content, conn=conn)
            PostsModel.increment_comment_count(post_id, conn=conn)
            conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("댓글 저장 실패 post_id=%s user_id=%s: %s", post_id, user_id, e)
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)

def get_comments(post_id: int, page: int = 1, size: int = 10) -> dict:
    if PostsModel.find_post_by_id(post_id) is None:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    rows = CommentsModel.get_comments_by_post_id(post_id, page, size)
    total_count = CommentsModel.get_comment_count_by_post_id(post_id)
    total_pages = max(1, (total_count + size - 1) // size) if total_count > 0 else 1

    result = []
    for row in rows:
        comment_row = {
            "id": row["id"],
            "post_id": row["post_id"],
            "author_id": row["author_id"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        author_row = {
            "id": row["author_user_id"],
            "nickname": row["author_nickname"],
            "profile_image_url": (row.get("author_profile_image_url") or "").strip() or "",
        }
        item = CommentResponse.from_rows(comment_row, author_row, post_id=post_id).model_dump(by_alias=True)
        result.append(item)
    payload = {
        "list": result,
        "totalCount": total_count,
        "totalPages": total_pages,
        "currentPage": page,
    }
    return success_response(ApiCode.COMMENTS_RETRIEVED, payload)

def update_comment(post_id: int, comment_id: int, data: CommentUpsertRequest) -> dict:
    affected = CommentsModel.update_comment(post_id, comment_id, data.content)
    if affected == 0:
        raise_http_error(404, ApiCode.COMMENT_NOT_FOUND)
    return success_response(ApiCode.COMMENT_UPDATED)

def withdraw_comment(post_id: int, comment_id: int) -> None:
    with get_connection() as conn:
        withdrawn = CommentsModel.withdraw_comment(post_id, comment_id, conn=conn)
        if not withdrawn:
            raise_http_error(404, ApiCode.COMMENT_NOT_FOUND)
        PostsModel.decrement_comment_count(post_id, conn=conn)
        conn.commit()
