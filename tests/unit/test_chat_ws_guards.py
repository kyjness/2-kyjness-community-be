"""WS DM 남용 방어 단위 테스트.

핵심 불변식: WS는 HTTP rate limit 미들웨어를 타지 않으므로 수신 루프에서 유저 단위
fixed-window(Redis 우선, 장애 시 인스턴스 로컬 폴백)로 막고, 차단 관계(방향 무관)면
방 생성·저장 전에 거부한다 — 차단 방향은 응답 문구로 노출하지 않는다.
"""

import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.common.exceptions import ForbiddenException
from app.core.middleware.rate_limit import check_fixed_window
from app.domain.chat.schema import ChatMessageSend
from app.domain.chat.service import ChatService
from app.domain.users.model import UsersModel
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


# --- check_fixed_window (공개 헬퍼) ---


class _FakeRedis:
    def __init__(self, count: int, ttl: int = 30, fail: bool = False) -> None:
        self._count = count
        self._ttl = ttl
        self._fail = fail
        self.calls: list[tuple] = []

    async def eval(self, script: str, numkeys: int, key: str, window: int):
        if self._fail:
            raise ConnectionError("redis down")
        self.calls.append((key, window))
        return [self._count, self._ttl]


async def test_check_fixed_window_allows_under_limit():
    redis = _FakeRedis(count=3)
    allowed, retry_after = await check_fixed_window(
        cast(Any, redis), f"t:{uuid.uuid4()}", window_sec=60, max_count=5
    )
    assert allowed and retry_after == 0


async def test_check_fixed_window_blocks_over_limit_with_retry_after():
    redis = _FakeRedis(count=6, ttl=42)
    allowed, retry_after = await check_fixed_window(
        cast(Any, redis), f"t:{uuid.uuid4()}", window_sec=60, max_count=5
    )
    assert not allowed
    assert retry_after == 42


async def test_check_fixed_window_falls_back_to_memory_on_redis_failure():
    key = f"t:{uuid.uuid4()}"
    redis = _FakeRedis(count=1, fail=True)
    for _ in range(2):
        allowed, _ = await check_fixed_window(cast(Any, redis), key, window_sec=60, max_count=2)
        assert allowed
    allowed, retry_after = await check_fixed_window(
        cast(Any, redis), key, window_sec=60, max_count=2
    )
    assert not allowed  # 메모리 폴백이 3번째 요청을 차단
    assert retry_after > 0


async def test_check_fixed_window_uses_memory_without_redis():
    key = f"t:{uuid.uuid4()}"
    allowed, _ = await check_fixed_window(None, key, window_sec=60, max_count=1)
    assert allowed
    allowed, _ = await check_fixed_window(None, key, window_sec=60, max_count=1)
    assert not allowed


# --- send_dm_from_ws 차단 검사 ---


class _NoopTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeDb:
    def begin(self) -> _NoopTx:
        return _NoopTx()


def _sess(db: _FakeDb) -> AsyncSession:
    return cast(AsyncSession, db)


async def test_send_dm_rejects_blocked_relation_before_room_creation(monkeypatch):
    sender, peer = uuid.uuid4(), uuid.uuid4()

    async def fake_get_user(user_id, *, db):
        return SimpleNamespace(status="ACTIVE")

    async def fake_block_exists(a, b, *, db):
        assert {a, b} == {sender, peer}
        return True

    async def fail_room(*args, **kwargs):
        raise AssertionError("차단 관계에서 방이 생성되면 안 된다")

    monkeypatch.setattr(UsersModel, "get_user_by_id", fake_get_user)
    monkeypatch.setattr(UsersModel, "block_exists_between", fake_block_exists)
    monkeypatch.setattr(ChatService, "get_or_create_room", fail_room)

    with pytest.raises(ForbiddenException) as exc:
        await ChatService.send_dm_from_ws(
            _sess(_FakeDb()),
            sender_id=sender,
            payload=ChatMessageSend(peer_user_id=peer, content="hi"),
            redis=None,
        )
    # 누가 차단했는지 방향을 노출하지 않는 중립 문구
    assert "차단" not in (exc.value.message or "")


async def test_block_exists_between_checks_both_directions():
    """방향 무관 술어인지 쿼리 구조로 고정(blocker/blocked 양방향 OR)."""
    import inspect

    src = inspect.getsource(UsersModel.block_exists_between.__func__)
    assert src.count("or_") >= 1
    assert src.count("blocker_id == user_a") == 1
    assert src.count("blocker_id == user_b") == 1
