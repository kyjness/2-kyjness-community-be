# app/core/validators.py
"""입력 검증 공통 (비밀번호/닉네임/프로필 이미지 URL 등)."""

import re
from typing import Optional

from app.core.config import settings

PASSWORD_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};\':\"\\|,.<>/?]")
NICKNAME_PATTERN = re.compile(r"^[가-힣a-zA-Z0-9]{1,10}$")


def validate_password_format(password: str) -> bool:
    if not password or not isinstance(password, str):
        return False
    if len(password) < 8 or len(password) > 20:
        return False
    return (
        bool(re.search(r"[A-Z]", password))
        and bool(re.search(r"[a-z]", password))
        and bool(re.search(r"[0-9]", password))
        and bool(PASSWORD_SPECIAL.search(password))
    )


def validate_nickname_format(nickname: str) -> bool:
    return bool(nickname and isinstance(nickname, str) and NICKNAME_PATTERN.match(nickname))


def validate_profile_image_url(url: Optional[str]) -> bool:
    """프로필 이미지 URL 형식 검증. None/빈 문자열은 허용."""
    if url is None or (isinstance(url, str) and not url.strip()):
        return True
    if not isinstance(url, str):
        return False
    return url.startswith("http://") or url.startswith("https://") or url.startswith(settings.BE_API_URL)
