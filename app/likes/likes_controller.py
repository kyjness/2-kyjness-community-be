# app/likes/likes_controller.py
"""좋아요 비즈니스 로직. 응답·에러는 core 사용."""

from app.likes.likes_model import LikesModel
from app.posts.posts_model import PostsModel
from app.core.response import success_response, raise_http_error


def create_like(post_id: int, user_id: int):
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    if LikesModel.has_liked(post_id, user_id):
        raise_http_error(400, "ALREADY_LIKED")
    like = LikesModel.create_like(post_id, user_id)
    if not like:
        raise_http_error(400, "ALREADY_LIKED")
    PostsModel.increment_like_count(post_id)
    updated_post = PostsModel.find_post_by_id(post_id)
    like_count = updated_post["likeCount"] if updated_post else 0
    return success_response("POSTLIKE_UPLOADED", {"likeCount": like_count})


def delete_like(post_id: int, user_id: int):
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    if not LikesModel.has_liked(post_id, user_id):
        raise_http_error(404, "LIKE_NOT_FOUND")
    LikesModel.delete_like(post_id, user_id)
    PostsModel.decrement_like_count(post_id)
    return success_response("LIKE_DELETED", None)
