# app/comments/comments_controller.py
"""댓글 비즈니스 로직. 권한(댓글 작성자)은 Route(require_comment_author), 응답은 core 사용."""

from app.comments.comments_model import CommentsModel
from app.posts.posts_model import PostsModel
from app.auth.auth_model import AuthModel
from app.core.response import success_response, raise_http_error


def create_comment(post_id: int, user_id: int, content: str):
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    comment = CommentsModel.create_comment(post_id, user_id, content)
    PostsModel.increment_comment_count(post_id)
    return success_response("COMMENT_UPLOADED", {"commentId": comment["commentId"]})


def get_comments(post_id: int, page: int = 1, size: int = 20):
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    comments = CommentsModel.get_comments_by_post_id(post_id, page, size)
    result = []
    for comment in comments:
        author = AuthModel.find_user_by_id(comment["authorId"])
        if author:
            result.append(
                {
                    "commentId": comment["commentId"],
                    "content": comment["content"],
                    "postId": post_id,
                    "author": {
                        "userId": author["userId"],
                        "nickname": author["nickname"],
                        "profileImageUrl": author.get("profileImageUrl", author.get("profileImage", "")),
                    },
                    "createdAt": comment["createdAt"],
                }
            )
    return success_response("COMMENTS_RETRIEVED", result)


def update_comment(post_id: int, comment_id: int, user_id: int, content: str):
    """댓글 수정. 게시글/댓글 존재·작성자 검사는 Route(require_comment_author)에서 수행."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    comment = CommentsModel.find_comment_by_id(comment_id)
    if not comment:
        raise_http_error(404, "COMMENT_NOT_FOUND")
    if comment["postId"] != post_id:
        raise_http_error(400, "INVALID_POSTID_FORMAT")
    CommentsModel.update_comment(comment_id, content)
    return success_response("COMMENT_UPDATED")


def delete_comment(post_id: int, comment_id: int, user_id: int):
    """댓글 삭제. 게시글/댓글 존재·작성자 검사는 Route(require_comment_author)에서 수행."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    comment = CommentsModel.find_comment_by_id(comment_id)
    if not comment:
        raise_http_error(404, "COMMENT_NOT_FOUND")
    if comment["postId"] != post_id:
        raise_http_error(400, "INVALID_POSTID_FORMAT")
    CommentsModel.delete_comment(comment_id)
    PostsModel.decrement_comment_count(post_id)
    return None
