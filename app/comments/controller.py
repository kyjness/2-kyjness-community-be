# app/comments/controller.py
"""댓글 비즈니스 로직."""

import logging

from fastapi import HTTPException

from app.comments.model import CommentsModel
from app.comments.schema import CommentCreateRequest, CommentUpdateRequest, CommentResponse, CommentAuthorInfo
from app.posts.model import PostsModel
from app.users.model import UsersModel
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error

logger = logging.getLogger(__name__)


def create_comment(post_id: int, user_id: int, data: CommentCreateRequest):
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    try:
        comment = CommentsModel.create_comment(post_id, user_id, data.content)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("댓글 저장 실패 post_id=%s user_id=%s: %s", post_id, user_id, e)
        raise
    PostsModel.increment_comment_count(post_id)
    return success_response(ApiCode.COMMENT_UPLOADED, {"commentId": comment["commentId"]})


def get_comments(post_id: int, page: int = 1, size: int = 10):
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, ApiCode.POST_NOT_FOUND)
    comments = CommentsModel.get_comments_by_post_id(post_id, page, size)
    total_count = CommentsModel.get_comment_count_by_post_id(post_id)
    total_pages = max(1, (total_count + size - 1) // size) if total_count > 0 else 1

    result = []
    for comment in comments:
        author = UsersModel.find_user_by_id(comment["authorId"])
        if author:
            item = CommentResponse(
                commentId=comment["commentId"],
                content=comment["content"],
                author=CommentAuthorInfo(
                    userId=author["userId"],
                    nickname=author["nickname"],
                    profileImageUrl=author.get("profileImageUrl", ""),
                ),
                createdAt=comment["createdAt"],
                postId=post_id,
            ).model_dump()
            result.append(item)
    return {
        "code": ApiCode.COMMENTS_RETRIEVED.value,
        "data": result,
        "totalCount": total_count,
        "totalPages": total_pages,
        "currentPage": page,
    }


def update_comment(post_id: int, comment_id: int, user_id: int, data: CommentUpdateRequest):
    CommentsModel.update_comment(comment_id, data.content)
    return success_response(ApiCode.COMMENT_UPDATED)


def withdraw_comment(post_id: int, comment_id: int, user_id: int):
    CommentsModel.withdraw_comment(comment_id)
    PostsModel.decrement_comment_count(post_id)
