# app/users/users_controller.py
from fastapi import HTTPException, UploadFile
from typing import Optional
import re
from app.users.users_model import UsersModel
from app.auth.auth_model import AuthModel

class UsersController:
    """사용자 정보 수정 관련 비즈니스 로직 처리"""
    
    # 비밀번호 형식 검증 (8-20자, 대문자/소문자/숫자/특수문자 각각 최소 1개 포함)
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 20
    
    # 닉네임 형식 검증 (1-10자, 공백 불가, 한글/영문/숫자만 허용)
    NICKNAME_PATTERN = re.compile(r'^[가-힣a-zA-Z0-9]{1,10}$')
    
    # URL 형식 검증
    URL_PATTERN = re.compile(r'^(http://|https://|\{BE-API-URL\})')
    
    # 프로필 이미지 업로드 관련 상수
    ALLOWED_PROFILE_IMAGE_TYPES = ["image/jpeg", "image/jpg"]  # .jpg만 허용
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @staticmethod
    def validate_password_format(password: str) -> bool:
        """비밀번호 형식 검증 (8-20자, 대문자/소문자/숫자/특수문자 각각 최소 1개 포함)"""
        if not password or not isinstance(password, str):
            return False
        
        # 길이 검증
        if len(password) < UsersController.MIN_PASSWORD_LENGTH or len(password) > UsersController.MAX_PASSWORD_LENGTH:
            return False
        
        # 대문자, 소문자, 숫자, 특수문자 각각 최소 1개 포함 검증
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'[0-9]', password))
        has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password))
        
        return has_upper and has_lower and has_digit and has_special
    
    @staticmethod
    def validate_nickname_format(nickname: str) -> bool:
        """닉네임 형식 검증"""
        if not nickname or not isinstance(nickname, str):
            return False
        return bool(UsersController.NICKNAME_PATTERN.match(nickname))
    
    @staticmethod
    def validate_profile_image_url(url: Optional[str]) -> bool:
        """프로필 이미지 URL 형식 검증"""
        if url is None:
            return True  # 선택 필드이므로 None 허용
        if not isinstance(url, str):
            return False
        if not url.strip():
            return True  # 빈 문자열도 허용 (기본 이미지 사용)
        return bool(UsersController.URL_PATTERN.match(url))
    
    @staticmethod
    def _is_valid_jpeg_image(file_content: bytes) -> bool:
        """JPEG 이미지 파일 유효성 검증 (매직 넘버 체크)"""
        if not file_content or len(file_content) < 2:
            return False
        # JPEG 매직 넘버 체크: FF D8로 시작해야 함
        return file_content[:2] == b'\xff\xd8'
    
    @staticmethod
    async def upload_profile_image(user_id: int, session_id: Optional[str], profile_image: UploadFile):
        """프로필 이미지 업로드 처리"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증
        authenticated_user_id = AuthModel.verify_token(session_id)
        if not authenticated_user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 403번
        # 다른 사용자 프로필 이미지 업로드 시도
        if authenticated_user_id != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})
        
        # status code 400번
        # user_id 형식 검증
        if not isinstance(user_id, int) or user_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_USERID_FORMAT", "data": None})
        
        # status code 400번
        # 파일 없음
        if not profile_image:
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # status code 400번
        # 파일 타입 검증 (.jpg만 허용)
        if profile_image.content_type not in UsersController.ALLOWED_PROFILE_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail={"code": "INVALID_FILE_TYPE", "data": None})
        
        # 파일 읽기
        file_content = await profile_image.read()
        
        # status code 400번
        # 파일이 비어있는지 확인
        if not file_content:
            raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE_FILE", "data": None})
        
        # status code 400번
        # 파일 크기 검증
        if len(file_content) > UsersController.MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail={"code": "FILE_SIZE_EXCEEDED", "data": None})
        
        # status code 400번
        # 이미지 형식 검증 (JPEG 매직 넘버 체크)
        if not UsersController._is_valid_jpeg_image(file_content):
            raise HTTPException(status_code=400, detail={"code": "UNSUPPORTED_IMAGE_FORMAT", "data": None})
        
        # 사용자 존재 확인
        user = UsersModel.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})
        
        # 파일 저장 및 URL 생성 (실제로는 파일을 저장하고 URL을 반환해야 하지만, 여기서는 Mock URL 반환)
        # 파일명은 사용자 ID를 기반으로 생성하여 중복 방지
        file_extension = "jpg"
        profile_image_url = f"{{BE-API-URL}}/public/image/profile/{user_id}.{file_extension}"
        
        # 프로필 이미지 URL 업데이트
        if not UsersModel.update_profile_image_url(user_id, profile_image_url):
            raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})
        
        # status code 201번(업로드 성공)
        return {
            "code": "PROFILE_IMAGE_UPLOADED",
            "data": {
                "profileImageUrl": profile_image_url
            }
        }
    
    @staticmethod
    def check_email(email: Optional[str]):
        """이메일 중복 체크"""
        # status code 400번
        # 이메일 입력 안했을 시
        if not email or not isinstance(email, str) or not email.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # 이메일 중복 확인
        is_available = not AuthModel.email_exists(email)
        
        # status code 200번
        return {
            "code": "EMAIL_AVAILABLE",
            "data": {
                "available": is_available
            }
        }
    
    @staticmethod
    def check_nickname(nickname: Optional[str]):
        """닉네임 중복 체크"""
        # status code 400번
        # 닉네임 입력 안했을 시
        if not nickname or not isinstance(nickname, str) or not nickname.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # 닉네임 형식 검증
        if not UsersController.validate_nickname_format(nickname):
            raise HTTPException(status_code=400, detail={"code": "INVALID_NICKNAME_FORMAT", "data": None})
        
        # 닉네임 중복 확인
        if AuthModel.nickname_exists(nickname):
            raise HTTPException(status_code=409, detail={"code": "NICKNAME_ALREADY_EXISTS", "data": None})
        
        # status code 200번
        return {
            "code": "NICKNAME_AVAILABLE",
            "data": {
                "available": True
            }
        }
    
    @staticmethod
    def get_user(user_id: int, session_id: Optional[str]):
        """내 정보 조회 처리"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증
        authenticated_user_id = AuthModel.verify_token(session_id)
        if not authenticated_user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 403번
        # 다른 사용자 정보 조회 시도
        if authenticated_user_id != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})
        
        # status code 400번
        # user_id 형식 검증
        if not isinstance(user_id, int) or user_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_USERID_FORMAT", "data": None})
        
        # 사용자 정보 조회
        user = UsersModel.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})
        
        # status code 200번(조회 성공)
        return {
            "code": "USER_RETRIEVED",
            "data": user
        }
    
    @staticmethod
    def update_user(user_id: int, session_id: Optional[str], nickname: Optional[str] = None, profile_image_url: Optional[str] = None):
        """내 정보 수정 처리"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증
        authenticated_user_id = AuthModel.verify_token(session_id)
        if not authenticated_user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 403번
        # 다른 사용자 정보 수정 시도
        if authenticated_user_id != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})
        
        # status code 400번
        # user_id 형식 검증
        if not isinstance(user_id, int) or user_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_USERID_FORMAT", "data": None})
        
        # 닉네임과 프로필 이미지 URL 둘 다 없으면 에러
        if nickname is None and profile_image_url is None:
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # 닉네임 검증 및 수정
        if nickname is not None:
            if not isinstance(nickname, str) or not nickname.strip():
                raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
            
            # 닉네임 형식 검증 (11자 이상 체크 포함)
            if len(nickname) > 10:
                raise HTTPException(status_code=400, detail={"code": "INVALID_NICKNAME_FORMAT", "data": None})
            
            # 공백 체크
            if ' ' in nickname:
                raise HTTPException(status_code=400, detail={"code": "INVALID_NICKNAME_FORMAT", "data": None})
            
            # 닉네임 형식 검증
            if not UsersController.validate_nickname_format(nickname):
                raise HTTPException(status_code=400, detail={"code": "INVALID_NICKNAME_FORMAT", "data": None})
            
            # 현재 사용자 정보 조회
            current_user = UsersModel.get_user_by_id(user_id)
            if not current_user:
                raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})
            
            # 현재 닉네임과 다르면 중복 확인
            if current_user["nickname"] != nickname:
                if AuthModel.nickname_exists(nickname):
                    raise HTTPException(status_code=409, detail={"code": "NICKNAME_ALREADY_EXISTS", "data": None})
                
                # 닉네임 수정
                if not UsersModel.update_nickname(user_id, nickname):
                    raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})
        
        # 프로필 이미지 URL 검증 및 수정
        if profile_image_url is not None:
            if not UsersController.validate_profile_image_url(profile_image_url):
                raise HTTPException(status_code=400, detail={"code": "INVALID_PROFILEIMAGEURL", "data": None})
            
            if not UsersModel.update_profile_image_url(user_id, profile_image_url):
                raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})
        
        # status code 200번(수정 성공)
        return {"code": "USER_UPDATED", "data": None}
    
    @staticmethod
    def update_password(user_id: int, session_id: Optional[str], current_password: str, new_password: str):
        """비밀번호 변경 처리"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증
        authenticated_user_id = AuthModel.verify_token(session_id)
        if not authenticated_user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 403번
        # 다른 사용자 비밀번호 변경 시도
        if authenticated_user_id != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})
        
        # status code 400번
        # user_id 형식 검증
        if not isinstance(user_id, int) or user_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_USERID_FORMAT", "data": None})
        
        # 현재 비밀번호 입력 안했을 시
        if not current_password or not isinstance(current_password, str) or not current_password.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # 새 비밀번호 입력 안했을 시
        if not new_password or not isinstance(new_password, str) or not new_password.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # 현재 비밀번호 형식 검증
        if not UsersController.validate_password_format(current_password):
            raise HTTPException(status_code=400, detail={"code": "INVALID_CURRENTPASSWORD_FORMAT", "data": None})
        
        # 새 비밀번호 형식 검증
        if not UsersController.validate_password_format(new_password):
            raise HTTPException(status_code=400, detail={"code": "INVALID_NEWPASSWORD_FORMAT", "data": None})
        
        # 사용자 존재 확인
        user = UsersModel.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})
        
        # 현재 비밀번호 확인 (해시화된 비밀번호와 비교)
        if not AuthModel.verify_password(user_id, current_password):
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 비밀번호 수정
        if not UsersModel.update_password(user_id, new_password):
            raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})
        
        # status code 200번(변경 성공)
        return {"code": "PASSWORD_UPDATED", "data": None}
    
    @staticmethod
    def withdraw_user(user_id: int, session_id: Optional[str]):
        """회원 탈퇴 처리"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증
        authenticated_user_id = AuthModel.verify_token(session_id)
        if not authenticated_user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 403번
        # 다른 사용자 탈퇴 시도
        if authenticated_user_id != user_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "data": None})
        
        # status code 400번
        # user_id 형식 검증
        if not isinstance(user_id, int) or user_id <= 0:
            raise HTTPException(status_code=400, detail={"code": "INVALID_USERID_FORMAT", "data": None})
        
        # 사용자 존재 확인
        user = UsersModel.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "data": None})
        
        # 회원 탈퇴
        if not UsersModel.delete_user(user_id):
            raise HTTPException(status_code=500, detail={"code": "INTERNAL_SERVER_ERROR", "data": None})
        
        # status code 204번(탈퇴 성공) - 응답 본문 없음
        return None
