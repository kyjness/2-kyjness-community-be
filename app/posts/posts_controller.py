# app/posts/posts_controller.py
from fastapi import HTTPException, UploadFile
from typing import Optional
from app.posts.posts_model import PostsModel
from app.auth.auth_model import AuthModel
from app.core.config import settings

"""게시글 관련 비즈니스 로직 처리 (함수형 컨트롤러)."""

# 이미지 파일 관련 상수
ALLOWED_IMAGE_TYPES = settings.ALLOWED_IMAGE_TYPES
MAX_FILE_SIZE = settings.MAX_FILE_SIZE


# 헬퍼 함수: 반복되는 코드 제거
def _raise_error(status_code: int, error_code: str) -> None:
    """에러 응답 생성 헬퍼 함수."""
    raise HTTPException(status_code=status_code, detail={"code": error_code, "data": None})


def _success_response(code: str, data=None):
    """성공 응답 생성 헬퍼 함수."""
    return {"code": code, "data": data}


def create_post(user_id: int, title: str, content: str, file_url: str = ""):
    """게시글 작성 처리."""
    # 파일 URL 형식 검증 (비즈니스 로직)
    if file_url and not (
        file_url.startswith("http://")
        or file_url.startswith("https://")
        or file_url.startswith(settings.BE_API_URL)
    ):
        _raise_error(400, "INVALID_FILE_URL")

    # 게시글 생성
    post = PostsModel.create_post(user_id, title, content, file_url)

    return _success_response("POST_UPLOADED", {"postId": post["postId"]})


async def upload_post_image(post_id: int, user_id: int, file: Optional[UploadFile]):
    """게시글 이미지 업로드 처리."""
    # 파일 없음
    if not file:
        _raise_error(400, "MISSING_REQUIRED_FIELD")

    # 게시글 존재 확인
    post = PostsModel.find_post_by_id(post_id)
    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 작성자가 아닌 경우
    if post["authorId"] != user_id:
        _raise_error(403, "FORBIDDEN")

    # 파일 타입 검증
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        _raise_error(400, "INVALID_FILE_TYPE")

    # 파일 읽기
    file_content = await file.read()

    # 파일이 비어있는지 확인
    if not file_content:
        _raise_error(400, "INVALID_IMAGE_FILE")

    # 파일 크기 검증
    if len(file_content) > MAX_FILE_SIZE:
        _raise_error(400, "FILE_SIZE_EXCEEDED")

    # 이미지 형식 검증 (매직 넘버 체크)
    if not _is_valid_image(file_content, file.content_type):
        _raise_error(400, "UNSUPPORTED_IMAGE_FORMAT")

    # 파일 저장 및 URL 생성 (실제로는 파일을 저장하고 URL을 반환해야 하지만, 여기서는 Mock URL 반환)
    file_url = f"{settings.BE_API_URL}/public/image/post/{post_id}_{file.filename}"

    # 게시글의 file_url 업데이트 (기능서 요구사항: 기존 이미지 파일로 저장되어 보여줌)
    PostsModel.update_post(post_id, title=None, content=None, file_url=file_url)

    return _success_response("POST_IMAGE_UPLOADED", {"postFileUrl": file_url})


def _is_valid_image(file_content: bytes, content_type: str) -> bool:
    """이미지 파일 유효성 검증 (매직 넘버 체크)."""
    if not file_content or len(file_content) < 8:
        return False

    # JPEG 매직 넘버 체크
    if content_type in ["image/jpeg", "image/jpg"]:
        return file_content[:2] == b'\xff\xd8'

    # PNG 매직 넘버 체크
    if content_type == "image/png":
        return file_content[:8] == b'\x89PNG\r\n\x1a\n'

    return True


def get_posts(page: int = 1, size: int = 10):
    """게시글 목록 조회 처리."""
    # Query parameter는 Route에서 이미 ge=1로 검증됨
    posts = PostsModel.get_all_posts(page, size)

    # 작성자 정보 추가
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

    return _success_response("POSTS_RETRIEVED", result)


def get_post(post_id: int):
    """게시글 상세 조회 처리."""
    post = PostsModel.find_post_by_id(post_id)

    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 조회수 증가
    PostsModel.increment_hits(post_id)

    # 작성자 정보 추가
    author = AuthModel.find_user_by_id(post["authorId"])
    if not author:
        _raise_error(404, "USER_NOT_FOUND")

    result = {
        "postId": post["postId"],
        "title": post["title"],
        "content": post["content"],
        "hits": post["hits"] + 1,  # 증가된 조회수 반영
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

    return _success_response("POST_RETRIEVED", result)


def update_post(
    post_id: int,
    user_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    file_url: Optional[str] = None,
):
    """게시글 수정 처리."""
    post = PostsModel.find_post_by_id(post_id)

    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 작성자 확인
    if post["authorId"] != user_id:
        _raise_error(403, "FORBIDDEN")

    # 파일 URL 형식 검증 (비즈니스 로직)
    if file_url is not None and file_url and not (
        file_url.startswith("http://")
        or file_url.startswith("https://")
        or file_url.startswith(settings.BE_API_URL)
    ):
        _raise_error(400, "INVALID_FILE_URL")

    # 게시글 수정
    PostsModel.update_post(post_id, title, content, file_url)

    return _success_response("POST_UPDATED")


def delete_post(post_id: int, user_id: int):
    """게시글 삭제 처리."""
    post = PostsModel.find_post_by_id(post_id)

    if not post:
        _raise_error(404, "POST_NOT_FOUND")

    # 작성자 확인
    if post["authorId"] != user_id:
        _raise_error(403, "FORBIDDEN")

    # 게시글 삭제
    PostsModel.delete_post(post_id)

    return None
