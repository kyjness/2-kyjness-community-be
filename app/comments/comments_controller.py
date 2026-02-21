# app/comments/comments_controller.py
"""댓글 비즈니스 로직. 권한(댓글 작성자)은 Route(require_comment_author), 응답은 core 사용."""

import logging

from fastapi import HTTPException

from app.comments.comments_model import CommentsModel
from app.comments.comments_schema import CommentCreateRequest, CommentUpdateRequest, CommentResponse, CommentAuthorInfo
from app.posts.posts_model import PostsModel
from app.users.users_model import UsersModel
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
    """댓글 목록 조회 (10개 단위 페이지네이션). totalCount, totalPages, currentPage 반환."""
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
    """댓글 수정. 게시글/댓글 존재·작성자 검사는 Route(require_comment_author)에서 이미 수행됨."""
    CommentsModel.update_comment(comment_id, data.content)
    return success_response(ApiCode.COMMENT_UPDATED)


def delete_comment(post_id: int, comment_id: int, user_id: int):
    """댓글 삭제. 게시글/댓글 존재·작성자 검사는 Route(require_comment_author)에서 이미 수행됨."""
    CommentsModel.delete_comment(comment_id)
    PostsModel.decrement_comment_count(post_id)
