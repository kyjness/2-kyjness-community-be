# 닉네임·비밀번호·UTC datetime 검증. ensure_* / UtcDatetime. DB naive datetime → API Z 포함.
import re
from datetime import datetime, timezone
from typing import Annotated, Optional

from pydantic import AfterValidator


def ensure_utc_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# 스키마에서 created_at 등에 사용. 매 모델마다 validator 반복 없이 타입만 지정하면 됨.
UtcDatetime = Annotated[datetime, AfterValidator(ensure_utc_datetime)]

PASSWORD_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};\':\"\\|,.<>/?]")
NICKNAME_PATTERN = re.compile(r"^[가-힣a-zA-Z0-9]{1,10}$")


def validate_password_format(password: str) -> bool:
    if not password or not isinstance(password, str):
        return False
    if len(password) < 8 or len(password) > 20:
        return False
    return (
        bool(re.search(r"[a-z]", password))
        and bool(re.search(r"[0-9]", password))
        and bool(PASSWORD_SPECIAL.search(password))
    )


def validate_nickname_format(nickname: str) -> bool:
    return bool(nickname and isinstance(nickname, str) and NICKNAME_PATTERN.match(nickname))


def ensure_password_format(v: str) -> str:
    if not validate_password_format(v):
        raise ValueError("INVALID_REQUEST_BODY")
    return v


def ensure_nickname_format(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("INVALID_REQUEST_BODY")
    if not validate_nickname_format(v.strip()):
        raise ValueError("INVALID_REQUEST_BODY")
    return v.strip()
