# 닉네임·비밀번호 형식 검증 (ensure_nickname_format, ensure_password_format).
import re
from typing import Optional

PASSWORD_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};\':\"\\|,.<>/?]")
NICKNAME_PATTERN = re.compile(r"^[가-힣a-zA-Z0-9]{1,10}$")


def normalize_image_content_type(ct: Optional[str]) -> str:
    if not (ct or "").strip():
        return "image/jpeg"
    ct = (ct or "").strip().lower()
    if ct in ("image/jpg", "image/pjpeg"):
        return "image/jpeg"
    return ct


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


def ensure_password_format(v: str) -> str:
    if not validate_password_format(v):
        raise ValueError("INVALID_PASSWORD_FORMAT")
    return v


def ensure_nickname_format(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("INVALID_NICKNAME_FORMAT")
    if not validate_nickname_format(v.strip()):
        raise ValueError("INVALID_NICKNAME_FORMAT")
    return v.strip()
