from fastapi import HTTPException, UploadFile
from typing import Optional
from app.models.posts_model import PostsModel
from app.models.auth_model import AuthModel
import os


class PostsController:
    """Posts 비즈니스 로직 처리"""

    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png"]
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    #게시글 작성
    @staticmethod
    def create_post(user_id: int, title: str, content: str, file_url: str = ""):
        # 필수 필드 검증
        if not title:
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        if not content:
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})

        # 형식 검증
        if not title.strip():
            raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
        if not content.strip():
            raise HTTPException(status_code=400, detail={"code": "INVALID_CONTENT_FORMAT", "data": None})
        if file_url and not (file_url.startswith("http://") or file_url.startswith("https://") or file_url.startswith(
                "{BE-API-URL}")):
            raise HTTPException(status_code=400, detail={"code": "INVALID_FILEURL", "data": None})

        # 게시글 생성
        post = PostsModel.create_post(user_id, title, content, file_url)

        return {"code": "POST_UPLOADED", "data": {"postId": post["postId"]}}

    #게시글 이미지 업로드
    @staticmethod
    async def upload_post_image(post_id: int, file: UploadFile):
        # 게시글 존재 확인
        post = PostsModel.find_post_by_id(post_id)
        if not post:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})

        # 파일 타입 검증
        if file.content_type not in PostsController.ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail={"code": "INVALID_FILE_TYPE", "data": None})

        # 파일 읽기
        file_content = await file.read()

        # 파일이 비어있는지 확인
        if not file_content:
            raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE_FILE", "data": None})

        # 파일 크기 검증
        if len(file_content) > PostsController.MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail={"code": "FILE_SIZE_EXCEEDED", "data": None})

        # 이미지 형식 검증 (간단한 헤더 체크)
        if not PostsController._is_valid_image(file_content, file.content_type):
            raise HTTPException(status_code=400, detail={"code": "UNSUPPORTED_IMAGE_FORMAT", "data": None})

        # 실제로는 파일을 저장하고 URL을 반환해야 하지만, 여기서는 Mock URL 반환
        file_url = f"{{BE-API-URL}}/public/image/post/{file.filename}"

        return {"code": "POST_IMAGE_UPLOADED", "data": {"postFileUrl": file_url}}

    #이미지 파일 유효성 검증
    @staticmethod
    def _is_valid_image(file_content: bytes, content_type: str) -> bool:
        if not file_content or len(file_content) < 8:
            return False

        # JPEG 매직 넘버 체크
        if content_type in ["image/jpeg", "image/jpg"]:
            return file_content[:2] == b'\xff\xd8'

        # PNG 매직 넘버 체크
        if content_type == "image/png":
            return file_content[:8] == b'\x89PNG\r\n\x1a\n'

        return True

    #게시글 목록 조회
    @staticmethod
    def get_posts(page: int = 1, size: int = 20):
        # 페이지 검증
        if page < 1:
            raise HTTPException(status_code=400, detail={"code": "INVALID_PAGE_VALUE", "data": None})
        if size < 1:
            raise HTTPException(status_code=400, detail={"code": "INVALID_SIZE_VALUE", "data": None})

        posts = PostsModel.get_all_posts(page, size)

        # 작성자 정보 추가
        result = []
        for post in posts:
            author = AuthModel.find_user_by_id(post["authorId"])
            if author:
                result.append({
                    "postId": post["postId"],
                    "title": post["title"],
                    "content": post["content"],
                    "hits": post["hits"],
                    "likeCount": post["likeCount"],
                    "commentCount": post["commentCount"],
                    "author": {
                        "userId": author["userId"],
                        "nickname": author["nickname"],
                        "profileImageUrl": author["profileImage"]
                    },
                    "createdAt": post["createdAt"]
                })

        return {"code": "POSTS_RETRIEVED", "data": result}

    #게시글 상세 조회
    @staticmethod
    def get_post(post_id: int):
        post = PostsModel.find_post_by_id(post_id)

        if not post:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})

        # 조회수 증가
        PostsModel.increment_hits(post_id)

        # 작성자 정보 추가
        author = AuthModel.find_user_by_id(post["authorId"])
        if not author:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})

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
                "profileImageUrl": author["profileImage"]
            },
            "file": post["file"],
            "createdAt": post["createdAt"]
        }

        return {"code": "POST_RETRIEVED", "data": result}

    #게시글 수정
    @staticmethod
    def update_post(user_id: int, post_id: int, title: Optional[str] = None,
                    content: Optional[str] = None, file_url: Optional[str] = None):
        post = PostsModel.find_post_by_id(post_id)

        if not post:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})

        # 작성자 확인
        if post["authorId"] != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})

        # 형식 검증
        if title is not None and not title.strip():
            raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
        if content is not None and not content.strip():
            raise HTTPException(status_code=400, detail={"code": "INVALID_CONTENT_FORMAT", "data": None})
        if file_url and not (file_url.startswith("http://") or file_url.startswith("https://") or file_url.startswith(
                "{BE-API-URL}")):
            raise HTTPException(status_code=400, detail={"code": "INVALID_FILEURL", "data": None})

        # 게시글 수정
        PostsModel.update_post(post_id, title, content, file_url)

        return {"code": "POST_UPDATED", "data": None}

    #게시글 삭제
    @staticmethod
    def delete_post(user_id: int, post_id: int):
        post = PostsModel.find_post_by_id(post_id)

        if not post:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})

        # 작성자 확인
        if post["authorId"] != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})

        # 게시글 삭제
        PostsModel.delete_post(post_id)

        return {"code": "POST_DELETED", "data": None}