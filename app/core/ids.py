# 애플리케이션 전역 ULID PK 생성. DB 컬럼은 CHAR(26) 권장.
from __future__ import annotations

import re

from ulid import ULID

_ULID_RE = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{25}$")


def new_ulid_str() -> str:
    """신규 엔티티 PK용 ULID 문자열(26자, Crockford Base32).

    동일 밀리초에 대량 생성되어도 타임스탬프(48bit)+랜덤(80bit) 구조상 충돌 확률은 무시 가능하다.
    단일 프로세스에서 동일 ms 연속 호출이 극도로 잦은 경우에만 Monotonic ULID 전용 라이브러리/확장을 고려한다.
    """
    return str(ULID())


def is_valid_ulid_str(value: str) -> bool:
    return bool(value and _ULID_RE.fullmatch(value))
