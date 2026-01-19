# app/users/users_controller.py
from fastapi import HTTPException, UploadFile
from typing import Optional
import re
from app.users.users_model import UsersModel
from app.auth.auth_model import AuthModel
from app.core.config import settings

"""사용자 관련 비즈니스 로직 처리 (함수형 컨트롤러)."""

# 비밀번호 형식 검증 (8-20자, 대문자/소문자/숫자/특수문자 각각 최소 1개 포함)
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 20

# 닉네임 형식 검증 (1-10자, 공백 불가, 한글/영문/숫자만 허용)
NICKNAME_PATTERN = re.compile(r'^[가-힣a-zA-Z0-9]{1,10}$')

# 프로필 이미지 업로드 관련 상수
ALLOWED_PROFILE_IMAGE_TYPES = ["image/jpeg", "image/jpg"]  # .jpg만 허용
MAX_FILE_SIZE = settings.MAX_FILE_SIZE  # config에서 가져옴


# 헬퍼 함수: 반복되는 코드 제거
def _raise_error(status_code: int, error_code: str) -> None:
    """에러 응답 생성 헬퍼 함수."""
    raise HTTPException(status_code=status_code, detail={"code": error_code, "data": None})


def _success_response(code: str, data=None):
    """성공 응답 생성 헬퍼 함수."""
    return {"code": code, "data": data}


def _get_url_pattern():
    """URL 패턴 생성 (config에서 BE_API_URL 가져오기)."""
    be_api_url_escaped = re.escape(settings.BE_API_URL)
    return re.compile(rf'^(http://|https://|{be_api_url_escaped})')


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


def _is_valid_jpeg_image(file_content: bytes) -> bool:
    """JPEG 이미지 파일 유효성 검증 (매직 넘버 체크)."""
    if not file_content or len(file_content) < 2:
        return False
    # JPEG 매직 넘버 체크: FF D8로 시작해야 함
    return file_content[:2] == b'\xff\xd8'


async def upload_profile_image(
    user_id: int,
    authenticated_user_id: int,
    profile_image: Optional[UploadFile],
):
    """프로필 이미지 업로드 처리."""
    # 다른 사용자 프로필 이미지 업로드 시도
    if authenticated_user_id != user_id:
        _raise_error(403, "FORBIDDEN")

    # 파일 없음
    if not profile_image:
        _raise_error(400, "MISSING_REQUIRED_FIELD")

    # 파일 타입 검증 (.jpg만 허용)
    if profile_image.content_type not in ALLOWED_PROFILE_IMAGE_TYPES:
        _raise_error(400, "INVALID_FILE_TYPE")

    # 파일 읽기
    file_content = await profile_image.read()

    # 파일이 비어있는지 확인
    if not file_content:
        _raise_error(400, "INVALID_IMAGE_FILE")

    # 파일 크기 검증
    if len(file_content) > MAX_FILE_SIZE:
        _raise_error(400, "FILE_SIZE_EXCEEDED")

    # 이미지 형식 검증 (JPEG 매직 넘버 체크)
    if not _is_valid_jpeg_image(file_content):
        _raise_error(400, "UNSUPPORTED_IMAGE_FORMAT")

    # 사용자 존재 확인
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        _raise_error(404, "USER_NOT_FOUND")

    # 파일 저장 및 URL 생성 (실제로는 파일을 저장하고 URL을 반환해야 하지만, 여기서는 Mock URL 반환)
    # 파일명은 사용자 ID를 기반으로 생성하여 중복 방지
    file_extension = "jpg"
    profile_image_url = f"{settings.BE_API_URL}/public/image/profile/{user_id}.{file_extension}"

    # 프로필 이미지 URL 업데이트
    if not UsersModel.update_profile_image_url(user_id, profile_image_url):
        _raise_error(500, "INTERNAL_SERVER_ERROR")

    return _success_response("PROFILE_IMAGE_UPLOADED", {"profileImageUrl": profile_image_url})


def check_email(email: Optional[str]):
    """이메일 중복 체크."""
    # 이메일 입력 안했을 시
    if not email or not isinstance(email, str) or not email.strip():
        _raise_error(400, "MISSING_REQUIRED_FIELD")

    # 이메일 중복 확인
    is_available = not AuthModel.email_exists(email)

    return _success_response("EMAIL_AVAILABLE", {"available": is_available})


def check_nickname(nickname: Optional[str]):
    """닉네임 중복 체크."""
    # 닉네임 입력 안했을 시
    if not nickname or not isinstance(nickname, str) or not nickname.strip():
        _raise_error(400, "MISSING_REQUIRED_FIELD")

    # 닉네임 형식 검증
    if not validate_nickname_format(nickname):
        _raise_error(400, "INVALID_NICKNAME_FORMAT")

    # 닉네임 중복 확인
    if AuthModel.nickname_exists(nickname):
        _raise_error(409, "NICKNAME_ALREADY_EXISTS")

    return _success_response("NICKNAME_AVAILABLE", {"available": True})


def get_user(user_id: int, authenticated_user_id: int):
    """내 정보 조회 처리."""
    # 다른 사용자 정보 조회 시도
    if authenticated_user_id != user_id:
        _raise_error(403, "FORBIDDEN")

    # 사용자 정보 조회
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        _raise_error(404, "USER_NOT_FOUND")

    return _success_response("USER_RETRIEVED", user)


def update_user(
    user_id: int,
    authenticated_user_id: int,
    nickname: Optional[str] = None,
    profile_image_url: Optional[str] = None,
):
    """내 정보 수정 처리."""
    # 다른 사용자 정보 수정 시도
    if authenticated_user_id != user_id:
        _raise_error(403, "FORBIDDEN")

    # 닉네임과 프로필 이미지 URL 둘 다 없으면 에러
    if nickname is None and profile_image_url is None:
        _raise_error(400, "MISSING_REQUIRED_FIELD")

    # 닉네임 검증 및 수정
    if nickname is not None:
        # 공백 체크 (비즈니스 로직)
        if ' ' in nickname:
            _raise_error(400, "INVALID_NICKNAME_FORMAT")

        # 닉네임 형식 검증 (비즈니스 로직: 한글/영문/숫자만)
        if not validate_nickname_format(nickname):
            _raise_error(400, "INVALID_NICKNAME_FORMAT")

        # 현재 사용자 정보 조회
        current_user = UsersModel.get_user_by_id(user_id)
        if not current_user:
            _raise_error(404, "USER_NOT_FOUND")

        # 현재 닉네임과 다르면 중복 확인
        if current_user["nickname"] != nickname:
            if AuthModel.nickname_exists(nickname):
                _raise_error(409, "NICKNAME_ALREADY_EXISTS")

            # 닉네임 수정
            if not UsersModel.update_nickname(user_id, nickname):
                _raise_error(500, "INTERNAL_SERVER_ERROR")

    # 프로필 이미지 URL 검증 및 수정
    if profile_image_url is not None:
        if not validate_profile_image_url(profile_image_url):
            _raise_error(400, "INVALID_PROFILEIMAGEURL")

        if not UsersModel.update_profile_image_url(user_id, profile_image_url):
            _raise_error(500, "INTERNAL_SERVER_ERROR")

    return _success_response("USER_UPDATED")


def update_password(
    user_id: int,
    authenticated_user_id: int,
    current_password: str,
    new_password: str,
):
    """비밀번호 변경 처리."""
    # 다른 사용자 비밀번호 변경 시도
    if authenticated_user_id != user_id:
        _raise_error(403, "FORBIDDEN")

    # 현재 비밀번호 형식 검증 (비즈니스 로직: 대문자/소문자/숫자/특수문자 각각 최소 1개)
    if not validate_password_format(current_password):
        _raise_error(400, "INVALID_CURRENTPASSWORD_FORMAT")

    # 새 비밀번호 형식 검증
    if not validate_password_format(new_password):
        _raise_error(400, "INVALID_NEWPASSWORD_FORMAT")

    # 사용자 존재 확인
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        _raise_error(404, "USER_NOT_FOUND")

    # 현재 비밀번호 확인 (해시화된 비밀번호와 비교)
    if not AuthModel.verify_password(user_id, current_password):
        _raise_error(401, "UNAUTHORIZED")

    # 비밀번호 수정
    if not UsersModel.update_password(user_id, new_password):
        _raise_error(500, "INTERNAL_SERVER_ERROR")

    return _success_response("PASSWORD_UPDATED")


def withdraw_user(user_id: int, authenticated_user_id: int):
    """회원 탈퇴 처리."""
    # 다른 사용자 탈퇴 시도
    if authenticated_user_id != user_id:
        _raise_error(403, "FORBIDDEN")

    # 사용자 존재 확인
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        _raise_error(404, "USER_NOT_FOUND")

    # 회원 탈퇴
    if not UsersModel.delete_user(user_id):
        _raise_error(500, "INTERNAL_SERVER_ERROR")

    return None
