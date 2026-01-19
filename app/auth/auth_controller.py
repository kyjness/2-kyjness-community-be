# app/auth/auth_controller.py
import logging
from fastapi import HTTPException
from typing import Optional
import re
from app.auth.auth_model import AuthModel
from app.core.config import settings

logger = logging.getLogger(__name__)

"""인증 관련 비즈니스 로직 처리 (함수형 컨트롤러).

FastAPI에서는 보통 라우트 함수 + 함수형(또는 service) 로직 조합이 관례적이라,
기존 class(staticmethod) 형태를 모듈 함수 형태로 정리했습니다.
"""

# 이메일 형식 검증 정규식 (일반적인 이메일 형식)
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# 비밀번호 형식 검증 (8-20자, 대문자/소문자/숫자/특수문자 각각 최소 1개 포함)
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 20

# 닉네임 형식 검증 (1-10자, 공백 불가, 한글/영문/숫자만 허용)
NICKNAME_PATTERN = re.compile(r'^[가-힣a-zA-Z0-9]{1,10}$')


def _get_url_pattern():
    """URL 패턴 생성 (config에서 BE_API_URL 가져오기)."""
    be_api_url_escaped = re.escape(settings.BE_API_URL)
    return re.compile(rf'^(http://|https://|{be_api_url_escaped})')


def validate_email_format(email: str) -> bool:
    """이메일 형식 검증."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_PATTERN.match(email))


def validate_password_format(password: str) -> bool:
    """비밀번호 형식 검증 (8-20자, 대문자/소문자/숫자/특수문자 각각 최소 1개 포함)."""
    if not password or not isinstance(password, str):
        return False

    # 길이 검증
    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        return False

    # 대문자, 소문자, 숫자, 특수문자 각각 최소 1개 포함 검증
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'[0-9]', password))
    has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password))

    return has_upper and has_lower and has_digit and has_special


def validate_nickname_format(nickname: str) -> bool:
    """닉네임 형식 검증."""
    if not nickname or not isinstance(nickname, str):
        return False
    return bool(NICKNAME_PATTERN.match(nickname))


def validate_profile_image_url(url: Optional[str]) -> bool:
    """프로필 이미지 URL 형식 검증."""
    if url is None:
        return True  # 선택 필드이므로 None 허용
    if not isinstance(url, str):
        return False
    if not url.strip():
        return True  # 빈 문자열도 허용 (기본 이미지 사용)
    return bool(_get_url_pattern().match(url))


# 헬퍼 함수: 반복되는 코드 제거
def _raise_error(status_code: int, error_code: str) -> None:
    """에러 응답 생성 헬퍼 함수."""
    raise HTTPException(status_code=status_code, detail={"code": error_code, "data": None})


def _success_response(code: str, data=None):
    """성공 응답 생성 헬퍼 함수."""
    return {"code": code, "data": data}


def signup(
    email: str,
    password: str,
    password_confirm: str,
    nickname: str,
    profile_image_url: Optional[str] = None,
):
    """회원가입 처리."""
    # 비밀번호 형식 검증
    if not validate_password_format(password):
        _raise_error(400, "INVALID_PASSWORD_FORMAT")

    # 비밀번호 확인 일치 검증
    if password != password_confirm:
        _raise_error(400, "PASSWORD_MISMATCH")

    # 닉네임 형식 검증
    if ' ' in nickname or not validate_nickname_format(nickname):
        _raise_error(400, "INVALID_NICKNAME_FORMAT")

    # 프로필 이미지 URL 형식 검증
    if not validate_profile_image_url(profile_image_url):
        _raise_error(400, "INVALID_PROFILEIMAGEURL")

    # 이메일 중복 확인
    if AuthModel.email_exists(email):
        _raise_error(409, "EMAIL_ALREADY_EXISTS")

    # 닉네임 중복 확인
    if AuthModel.nickname_exists(nickname):
        _raise_error(409, "NICKNAME_ALREADY_EXISTS")

    # 사용자 생성
    AuthModel.create_user(email, password, nickname, profile_image_url)

    return _success_response("SIGNUP_SUCCESS")


def login(email: str, password: str):
    """로그인 처리."""
    # 비밀번호 형식 검증
    if not validate_password_format(password):
        _raise_error(400, "INVALID_PASSWORD_FORMAT")

    # 사용자 찾기
    user = AuthModel.find_user_by_email(email)
    if not user:
        logger.warning(f"Login failed: User not found (email provided)")
        _raise_error(401, "INVALID_CREDENTIALS")

    # 비밀번호 확인
    if not AuthModel.verify_password(user["userId"], password):
        logger.warning(f"Login failed: Invalid password (user_id={user['userId']})")
        _raise_error(401, "INVALID_CREDENTIALS")

    # 세션 ID 생성
    session_id = AuthModel.create_token(user["userId"])

    return _success_response("LOGIN_SUCCESS", {
        "userId": user["userId"],
        "email": user["email"],
        "nickname": user["nickname"],
        "authToken": session_id,  # API 명세서에 따라 authToken 포함 (실제 인증은 쿠키의 session_id 사용)
        "profileImage": user["profileImageUrl"],
    })


def logout(session_id: Optional[str]):
    """로그아웃 처리 (쿠키-세션 방식)."""
    # 세션 ID 삭제 (인증은 Dependency에서 이미 검증됨)
    AuthModel.revoke_token(session_id)

    return _success_response("LOGOUT_SUCCESS")


def get_me(user_id: int):
    """현재 로그인한 사용자 정보 조회 (쿠키-세션 방식)."""
    user = AuthModel.find_user_by_id(user_id)
    if not user:
        _raise_error(401, "UNAUTHORIZED")

    return _success_response("AUTH_SUCCESS", {
        "userId": user["userId"],
        "email": user["email"],
        "nickname": user["nickname"],
        "profileImageUrl": user["profileImageUrl"],
    })
