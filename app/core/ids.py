# 엔티티 PK: UUID v7(PostgreSQL native). 비엔티티 토큰·추적 ID는 ULID 문자열 유지(jti, request_id 등).
from __future__ import annotations

import re
from typing import cast
from uuid import UUID

from ulid import ULID
from uuid_extensions import uuid7

_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_BASE62_INDEX: dict[str, int] = {c: i for i, c in enumerate(_BASE62)}
_ULID_RE = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{25}$")


def new_uuid7() -> UUID:
    return cast(UUID, uuid7())


def new_ulid_str() -> str:
    return str(ULID())


def is_valid_ulid_str(value: str) -> bool:
    return bool(value and _ULID_RE.fullmatch(value))


def uuid_to_base62(u: UUID) -> str:
    n = u.int
    if n == 0:
        return _BASE62[0]
    out: list[str] = []
    while n:
        n, r = divmod(n, 62)
        out.append(_BASE62[r])
    return "".join(reversed(out))


def base62_to_uuid(s: str) -> UUID:
    if not isinstance(s, str) or not (s := s.strip()):
        raise ValueError("empty_base62")
    n = 0
    for ch in s:
        idx = _BASE62_INDEX.get(ch)
        if idx is None:
            raise ValueError("invalid_base62_char")
        n = n * 62 + idx
        if n.bit_length() > 128:
            raise ValueError("base62_overflow")
    return UUID(int=n)


def ulid_str_to_uuid(s: str) -> UUID:
    if not is_valid_ulid_str(s):
        raise ValueError("invalid_ulid")
    return ULID.from_str(s).to_uuid()


def jwt_sub_to_uuid(sub: str) -> UUID:
    """JWT sub: Base62(신규) · UUID 문자열 · 레거시 ULID."""
    raw = (sub or "").strip()
    if not raw:
        raise ValueError("empty_sub")
    try:
        return UUID(raw)
    except ValueError:
        pass
    try:
        return base62_to_uuid(raw)
    except ValueError:
        pass
    return ulid_str_to_uuid(raw)


def parse_public_id_value(v: object) -> UUID:
    """Pydantic BeforeValidator: ORM UUID, UUID 문자열, Base62, 레거시 ULID."""
    if isinstance(v, UUID):
        return v
    if not isinstance(v, str):
        raise ValueError("public_id_type")
    s = v.strip()
    if not s:
        raise ValueError("public_id_empty")
    try:
        return UUID(s)
    except ValueError:
        pass
    try:
        return base62_to_uuid(s)
    except ValueError:
        pass
    return ulid_str_to_uuid(s)


def parse_optional_public_id_value(v: object) -> UUID | None:
    if v is None:
        return None
    return parse_public_id_value(v)
