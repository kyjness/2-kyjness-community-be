# app/posts/posts_controller.py
"""게시글 비즈니스 로직. 권한(작성자)은 Route(require_post_author), 검증·응답은 core 사용."""

from typing import Optional

from fastapi import UploadFile

from app.posts.posts_model import PostsModel
from app.auth.auth_model import AuthModel
from app.core.config import settings
from app.core.response import success_response, raise_http_error
from app.core.file_upload import validate_image_upload, POST_ALLOWED_TYPES, MAX_FILE_SIZE


def create_post(user_id: int, title: str, content: str, file_url: str = ""):
    if file_url and not (
        file_url.startswith("http://")
        or file_url.startswith("https://")
        or file_url.startswith(settings.BE_API_URL)
    ):
        raise_http_error(400, "INVALID_FILE_URL")
    post = PostsModel.create_post(user_id, title, content, file_url)
    return success_response("POST_UPLOADED", {"postId": post["postId"]})


async def upload_post_image(post_id: int, user_id: int, file: Optional[UploadFile]):
    """게시글 이미지 업로드. 게시글 존재·작성자 검사는 Route(require_post_author)에서 수행."""
    if not file:
        raise_http_error(400, "MISSING_REQUIRED_FIELD")
    await validate_image_upload(file, POST_ALLOWED_TYPES, MAX_FILE_SIZE)
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    file_url = f"{settings.BE_API_URL}/public/image/post/{post_id}_{file.filename}"
    PostsModel.update_post(post_id, title=None, content=None, file_url=file_url)
    return success_response("POST_IMAGE_UPLOADED", {"postFileUrl": file_url})


def get_posts(page: int = 1, size: int = 10):
    posts = PostsModel.get_all_posts(page, size)
    result = []
    for post in posts:
        author = AuthModel.find_user_by_id(post["authorId"])
        if author:
            result.append(
                {
                    "postId": post["postId"],
                    "title": post["title"],
                    "content": post["content"],
                    "hits": post["hits"],
                    "likeCount": post["likeCount"],
                    "commentCount": post["commentCount"],
                    "author": {
                        "userId": author["userId"],
                        "nickname": author["nickname"],
                        "profileImageUrl": author.get("profileImageUrl", author.get("profileImage", "")),
                    },
                    "file": post.get("file"),
                    "createdAt": post["createdAt"],
                }
            )
    return success_response("POSTS_RETRIEVED", result)


def get_post(post_id: int):
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    PostsModel.increment_hits(post_id)
    author = AuthModel.find_user_by_id(post["authorId"])
    if not author:
        raise_http_error(404, "USER_NOT_FOUND")
    result = {
        "postId": post["postId"],
        "title": post["title"],
        "content": post["content"],
        "hits": post["hits"] + 1,
        "likeCount": post["likeCount"],
        "commentCount": post["commentCount"],
        "author": {
            "userId": author["userId"],
            "nickname": author["nickname"],
            "profileImageUrl": author.get("profileImageUrl", author.get("profileImage", "")),
        },
        "file": post.get("file"),
        "createdAt": post["createdAt"],
    }
    return success_response("POST_RETRIEVED", result)


def update_post(
    post_id: int,
    user_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    file_url: Optional[str] = None,
):
    """게시글 수정. 작성자 검사는 Route(require_post_author)에서 수행."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    if file_url is not None and file_url and not (
        file_url.startswith("http://")
        or file_url.startswith("https://")
        or file_url.startswith(settings.BE_API_URL)
    ):
        raise_http_error(400, "INVALID_FILE_URL")
    PostsModel.update_post(post_id, title, content, file_url)
    return success_response("POST_UPDATED")


def delete_post(post_id: int, user_id: int):
    """게시글 삭제. 작성자 검사는 Route(require_post_author)에서 수행."""
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        raise_http_error(404, "POST_NOT_FOUND")
    PostsModel.delete_post(post_id)
    return None
