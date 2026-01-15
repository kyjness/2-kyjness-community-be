# app/auth/auth_controller.py
from fastapi import HTTPException
from typing import Optional
import re
from app.auth.auth_model import AuthModel

class AuthController:
    """인증 관련 비즈니스 로직 처리"""
    
    # 이메일 형식 검증 정규식 (일반적인 이메일 형식)
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    # 비밀번호 형식 검증 (8-20자, 대문자/소문자/숫자/특수문자 각각 최소 1개 포함)
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 20
    
    # 닉네임 형식 검증 (1-10자, 공백 불가, 한글/영문/숫자만 허용)
    NICKNAME_PATTERN = re.compile(r'^[가-힣a-zA-Z0-9]{1,10}$')
    
    # URL 형식 검증
    URL_PATTERN = re.compile(r'^(http://|https://|\{BE-API-URL\})')
    
    @staticmethod
    def validate_email_format(email: str) -> bool:
        """이메일 형식 검증"""
        if not email or not isinstance(email, str):
            return False
        return bool(AuthController.EMAIL_PATTERN.match(email))
    
    @staticmethod
    def validate_password_format(password: str) -> bool:
        """비밀번호 형식 검증 (8-20자, 대문자/소문자/숫자/특수문자 각각 최소 1개 포함)"""
        if not password or not isinstance(password, str):
            return False
        
        # 길이 검증
        if len(password) < AuthController.MIN_PASSWORD_LENGTH or len(password) > AuthController.MAX_PASSWORD_LENGTH:
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
        return bool(AuthController.NICKNAME_PATTERN.match(nickname))
    
    @staticmethod
    def validate_profile_image_url(url: Optional[str]) -> bool:
        """프로필 이미지 URL 형식 검증"""
        if url is None:
            return True  # 선택 필드이므로 None 허용
        if not isinstance(url, str):
            return False
        if not url.strip():
            return True  # 빈 문자열도 허용 (기본 이미지 사용)
        return bool(AuthController.URL_PATTERN.match(url))
    
    @staticmethod
    def check_rate_limit(identifier: str):
        """Rate limiting 확인"""
        # status code 429번
        # 요청 과다
        if not AuthModel.check_rate_limit(identifier):
            raise HTTPException(status_code=429, detail={"code": "RATE_LIMIT_EXCEEDED", "data": None})
    
    @staticmethod
    def signup(email: str, password: str, password_confirm: str, nickname: str, profile_image_url: Optional[str] = None, identifier: Optional[str] = None):
        """회원가입 처리"""
        # status code 429번
        # Rate limiting 확인 (요청 과다 체크)
        if identifier:
            AuthController.check_rate_limit(identifier)
        
        # status code 400번
        # 필수 필드 검증
        if not email or not isinstance(email, str) or not email.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        if not password or not isinstance(password, str) or not password.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        if not password_confirm or not isinstance(password_confirm, str) or not password_confirm.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        if not nickname or not isinstance(nickname, str) or not nickname.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # 이메일 형식 검증
        if not AuthController.validate_email_format(email):
            raise HTTPException(status_code=400, detail={"code": "INVALID_EMAIL_FORMAT", "data": None})
        
        # 비밀번호 형식 검증
        if not AuthController.validate_password_format(password):
            raise HTTPException(status_code=400, detail={"code": "INVALID_PASSWORD_FORMAT", "data": None})
        
        # 비밀번호 확인 일치 검증
        if password != password_confirm:
            raise HTTPException(status_code=400, detail={"code": "PASSWORD_MISMATCH", "data": None})
        
        # 닉네임 형식 검증 (공백 체크 포함)
        if ' ' in nickname:
            raise HTTPException(status_code=400, detail={"code": "INVALID_NICKNAME_FORMAT", "data": None})
        if not AuthController.validate_nickname_format(nickname):
            raise HTTPException(status_code=400, detail={"code": "INVALID_NICKNAME_FORMAT", "data": None})
        
        # 프로필 이미지 URL 형식 검증
        if not AuthController.validate_profile_image_url(profile_image_url):
            raise HTTPException(status_code=400, detail={"code": "INVALID_PROFILEIMAGEURL", "data": None})
        
        #status code 409번
        # 이메일 중복 확인
        if AuthModel.email_exists(email):
            raise HTTPException(status_code=409, detail={"code": "EMAIL_ALREADY_EXISTS", "data": None})
        
        # 닉네임 중복 확인
        if AuthModel.nickname_exists(nickname):
            raise HTTPException(status_code=409, detail={"code": "NICKNAME_ALREADY_EXISTS", "data": None})
        
        # 사용자 생성
        user = AuthModel.create_user(email, password, nickname, profile_image_url)
        
        # status code 201번(회원가입 성공)
        return {"code": "SIGNUP_SUCCESS", "data": None}
    
    @staticmethod
    def login(email: str, password: str, identifier: Optional[str] = None):
        """로그인 처리"""
        # status code 429번
        # Rate limiting 확인 (요청 과다 체크)
        if identifier:
            AuthController.check_rate_limit(identifier)
        
        # status code 400번
        # 필수 필드 검증
        if not email or not isinstance(email, str) or not email.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        if not password or not isinstance(password, str) or not password.strip():
            raise HTTPException(status_code=400, detail={"code": "MISSING_REQUIRED_FIELD", "data": None})
        
        # 이메일 형식 검증
        if not AuthController.validate_email_format(email):
            raise HTTPException(status_code=400, detail={"code": "INVALID_EMAIL_FORMAT", "data": None})
        
        # 비밀번호 형식 검증
        if not AuthController.validate_password_format(password):
            raise HTTPException(status_code=400, detail={"code": "INVALID_PASSWORD_FORMAT", "data": None})
        
        # 사용자 찾기
        user = AuthModel.find_user_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "data": None})
        
        # 비밀번호 확인 (해시화된 비밀번호와 비교)
        if not AuthModel.verify_password(user["userId"], password):
            raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "data": None})
        
        # 세션 ID 생성 (쿠키-세션 방식)
        session_id = AuthModel.create_token(user["userId"])
        
        # status code 200번(로그인 성공)
        return {
            "code": "LOGIN_SUCCESS",
            "data": {
                "userId": user["userId"],
                "email": user["email"],
                "nickname": user["nickname"],
                "authToken": session_id,  # API 명세서에 따라 authToken 포함 (실제 인증은 쿠키의 session_id 사용)
                "profileImage": user["profileImageUrl"]
            }
        }
    
    @staticmethod
    def logout(session_id: Optional[str]):
        """로그아웃 처리 (쿠키-세션 방식)"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증 실패
        user_id = AuthModel.verify_token(session_id)
        if not user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 삭제
        AuthModel.revoke_token(session_id)
        
        # status code 200번(로그아웃 성공)
        return {"code": "LOGOUT_SUCCESS", "data": None}
    
    @staticmethod
    def get_me(session_id: Optional[str]):
        """현재 로그인한 사용자 정보 조회 (쿠키-세션 방식)"""
        # status code 401번
        # 인증 정보 없음
        if not session_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 세션 ID 검증 실패
        user_id = AuthModel.verify_token(session_id)
        if not user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # 사용자 정보 조회 실패
        user = AuthModel.find_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # status code 200번(로그인 상태 체크 성공)
        return {
            "code": "AUTH_SUCCESS",
            "data": {
                "userId": user["userId"],
                "email": user["email"],
                "nickname": user["nickname"],
                "profileImageUrl": user["profileImageUrl"]
            }
        }
    
    @staticmethod
    def verify_token(authorization: Optional[str]) -> int:
        """Authorization 헤더에서 세션 ID 검증 및 사용자 ID 반환"""
        if not authorization:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        # "Bearer " 접두사 제거
        session_id = authorization.replace("Bearer ", "").strip() if authorization else None
        
        user_id = AuthModel.verify_token(session_id)
        if not user_id:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "data": None})
        
        return user_id
