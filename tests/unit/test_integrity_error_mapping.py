"""IntegrityError 전역 핸들러의 PostgreSQL 매핑 단위 테스트.

SQLSTATE(23505 unique·23503 FK)와 psycopg diag의 제약명으로 응답 코드를 결정한다 —
psycopg v3 예외의 실제 속성은 sqlstate다(pgcode는 v2 잔재 — 가짜 예외도 실 드라이버와
같은 속성을 써야 결함을 은폐하지 않는다). 에러 메시지 문자열 파싱은 로케일·드라이버
포맷에 취약해 쓰지 않는다.
"""

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.core.exception_handlers import register_exception_handlers
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

pytestmark = pytest.mark.asyncio


def _integrity_error(sqlstate: str | None, constraint: str | None = None) -> IntegrityError:
    orig = SimpleNamespace(sqlstate=sqlstate, diag=SimpleNamespace(constraint_name=constraint))
    return IntegrityError("stmt", {}, orig)  # type: ignore[arg-type]


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/t", "headers": []})


async def _handle(exc: IntegrityError):
    app = FastAPI()
    register_exception_handlers(app)
    handler = cast(Any, app.exception_handlers[IntegrityError])  # 등록된 async 핸들러
    resp = await handler(_request(), exc)
    return resp.status_code, json.loads(bytes(resp.body))["code"]


async def test_unique_violation_maps_by_constraint_name():
    assert await _handle(_integrity_error("23505", "uq_users_email")) == (
        409,
        "EMAIL_ALREADY_EXISTS",
    )
    assert await _handle(_integrity_error("23505", "users_nickname_key")) == (
        409,
        "NICKNAME_ALREADY_EXISTS",
    )
    assert await _handle(_integrity_error("23505", "uq_chat_rooms_user_pair")) == (409, "CONFLICT")


async def test_fk_violation_maps_to_constraint_error():
    assert await _handle(_integrity_error("23503", "fk_posts_author")) == (409, "CONSTRAINT_ERROR")


async def test_other_integrity_maps_to_invalid_request():
    # sqlstate 없음(드라이버 외 예외)·기타 코드는 400 일반 매핑
    assert (await _handle(_integrity_error(None)))[0] == 400
    assert (await _handle(_integrity_error("23514")))[0] == 400  # check_violation
