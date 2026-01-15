# app/posts/posts_controller.py
from fastapi import HTTPException, UploadFile
from typing import Optional
from app.posts.posts_model import PostsModel
from app.auth.auth_model import AuthModel

class PostsController:
    """Posts 비즈니스 로직 처리"""

    # 제목 최대 길이 (기능서 요구사항: 최대 26자)
    MAX_TITLE_LENGTH = 26
    
    # 이미지 파일 관련 상수
    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/jpg", "image/png"]
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @staticmethod
    def create_post(user_id: int, title: str, content: str, file_url: str = ""):
        """게시글 작성 처리"""
        # status code 400번
        # 필수 필드 검증
        if not title or not isinstance(title, str) or not title.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        if not content or not isinstance(content, str) or not content.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # status code 400번
        # 제목 길이 검증 (최대 26자)
        if len(title) > PostsController.MAX_TITLE_LENGTH:
            raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
        
        # status code 400번
        # 파일 URL 형식 검증
        if file_url and not (file_url.startswith("http://") or file_url.startswith("https://") or file_url.startswith("{BE-API-URL}")):
            raise HTTPException(status_code=400, detail={"code": "INVALID_FILEURL", "data": None})

        # 게시글 생성
        post = PostsModel.create_post(user_id, title, content, file_url)

        # status code 201번(작성 성공)
        return {"code": "POST_UPLOADED", "data": {"postId": post["postId"]}}

    @staticmethod
    async def upload_post_image(post_id: int, session_id: Optional[str], file: UploadFile):
        """게시글 이미지 업로드 처리"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증
        authenticated_user_id = AuthModel.verify_token(session_id)
        if not authenticated_user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 400번
        # post_id 형식 검증
        if not isinstance(post_id, int) or post_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_POSTID_FORMAT", "data": None})
        
        # 게시글 존재 확인
        post = PostsModel.find_post_by_id(post_id)
        if not post:
            raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "data": None})
        
        # status code 403번
        # 작성자가 아닌 경우
        if post["authorId"] != authenticated_user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})

        # status code 400번
        # 파일 타입 검증
        if file.content_type not in PostsController.ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail={"code": "INVALID_FILE_TYPE", "data": None})

        # 파일 읽기
        file_content = await file.read()

        # status code 400번
        # 파일이 비어있는지 확인
        if not file_content:
            raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE_FILE", "data": None})

        # status code 400번
        # 파일 크기 검증
        if len(file_content) > PostsController.MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail={"code": "FILE_SIZE_EXCEEDED", "data": None})

        # status code 400번
        # 이미지 형식 검증 (매직 넘버 체크)
        if not PostsController._is_valid_image(file_content, file.content_type):
            raise HTTPException(status_code=400, detail={"code": "UNSUPPORTED_IMAGE_FORMAT", "data": None})

        # 파일 저장 및 URL 생성 (실제로는 파일을 저장하고 URL을 반환해야 하지만, 여기서는 Mock URL 반환)
        file_url = f"{{BE-API-URL}}/public/image/post/{post_id}_{file.filename}"

        # 게시글의 file_url 업데이트 (기능서 요구사항: 기존 이미지 파일로 저장되어 보여줌)
        PostsModel.update_post(post_id, title=None, content=None, file_url=file_url)

        # status code 201번(업로드 성공)
        return {"code": "POST_IMAGE_UPLOADED", "data": {"postFileUrl": file_url}}

    @staticmethod
    def _is_valid_image(file_content: bytes, content_type: str) -> bool:
        """이미지 파일 유효성 검증 (매직 넘버 체크)"""
        if not file_content or len(file_content) < 8:
            return False

        # JPEG 매직 넘버 체크
        if content_type in ["image/jpeg", "image/jpg"]:
            return file_content[:2] == b'\xff\xd8'

        # PNG 매직 넘버 체크
        if content_type == "image/png":
            return file_content[:8] == b'\x89PNG\r\n\x1a\n'

        return True

    @staticmethod
    def get_posts(page: int = 1, size: int = 10):
        """게시글 목록 조회 처리"""
        # status code 400번
        # 페이지 검증
        if not isinstance(page, int) or page < 1:
            raise HTTPException(status_code=400, detail={"code": "INVALID_PAGE_VALUE", "data": None})
        if not isinstance(size, int) or size < 1:
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
                        "profileImageUrl": author.get("profileImageUrl", author.get("profileImage", ""))
                    },
                    "file": post.get("file"),
                    "createdAt": post["createdAt"]
                })

        # status code 200번(조회 성공)
        return {"code": "POSTS_RETRIEVED", "data": result}

    @staticmethod
    def get_post(post_id: int):
        """게시글 상세 조회 처리"""
        # status code 400번
        # post_id 형식 검증
        if not isinstance(post_id, int) or post_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_POSTID_FORMAT", "data": None})
        
        post = PostsModel.find_post_by_id(post_id)

        if not post:
            raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "data": None})

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
                "profileImageUrl": author.get("profileImageUrl", author.get("profileImage", ""))
            },
            "file": post.get("file"),
            "createdAt": post["createdAt"]
        }

        # status code 200번(조회 성공)
        return {"code": "POST_RETRIEVED", "data": result}

    @staticmethod
    def update_post(user_id: int, post_id: int, session_id: Optional[str], title: Optional[str] = None,
                    content: Optional[str] = None, file_url: Optional[str] = None):
        """게시글 수정 처리"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증
        authenticated_user_id = AuthModel.verify_token(session_id)
        if not authenticated_user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 403번
        # 다른 사용자 게시글 수정 시도
        if authenticated_user_id != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})
        
        # status code 400번
        # post_id 형식 검증
        if not isinstance(post_id, int) or post_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_POSTID_FORMAT", "data": None})
        
        post = PostsModel.find_post_by_id(post_id)

        if not post:
            raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "data": None})

        # status code 403번
        # 작성자 확인
        if post["authorId"] != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})

        # status code 400번
        # 형식 검증
        if title is not None:
            if not isinstance(title, str) or not title.strip():
                raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
            # 제목 길이 검증 (최대 26자)
            if len(title) > PostsController.MAX_TITLE_LENGTH:
                raise HTTPException(status_code=400, detail={"code": "INVALID_TITLE_FORMAT", "data": None})
        
        if content is not None:
            if not isinstance(content, str) or not content.strip():
                raise HTTPException(status_code=400, detail={"code": "INVALID_CONTENT_FORMAT", "data": None})
        
        if file_url is not None and file_url and not (file_url.startswith("http://") or file_url.startswith("https://") or file_url.startswith("{BE-API-URL}")):
            raise HTTPException(status_code=400, detail={"code": "INVALID_FILEURL", "data": None})

        # 게시글 수정
        PostsModel.update_post(post_id, title, content, file_url)

        # status code 200번(수정 성공)
        return {"code": "POST_UPDATED", "data": None}

    @staticmethod
    def delete_post(user_id: int, post_id: int, session_id: Optional[str]):
        """게시글 삭제 처리"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증
        authenticated_user_id = AuthModel.verify_token(session_id)
        if not authenticated_user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 403번
        # 다른 사용자 게시글 삭제 시도
        if authenticated_user_id != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})
        
        # status code 400번
        # post_id 형식 검증
        if not isinstance(post_id, int) or post_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_POSTID_FORMAT", "data": None})
        
        post = PostsModel.find_post_by_id(post_id)

        if not post:
            raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "data": None})

        # status code 403번
        # 작성자 확인
        if post["authorId"] != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})

        # 게시글 삭제
        PostsModel.delete_post(post_id)

        # status code 204번(삭제 성공) - 응답 본문 없음
        return None
