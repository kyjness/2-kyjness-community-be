"""알림 SSE 팬아웃(chat 동형) 단위 테스트.

핵심 불변식: SSE 연결은 Redis pubsub을 점유하지 않고(공유 풀 고갈 방지) 로컬 큐로 대기하며,
발행은 단일 채널 envelope → 공용 리스너가 채널별 핸들러로 디스패치, publish 실패 시
같은 인스턴스 수신자는 로컬로 폴백 전달된다.
"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest
from app.domain.chat.service import ChatService
from app.domain.notifications.service import NotificationService
from app.domain.notifications.stream import (
    NOTIF_SSE_FANOUT_CHANNEL,
    SseFanoutManager,
    notification_sse_manager,
)
from app.infra import pubsub as pubsub_mod
from app.infra.pubsub import publish_user_envelope, run_user_fanout_listener

pytestmark = pytest.mark.asyncio


class _FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> int:
        if self.fail:
            raise ConnectionError("redis down")
        self.published.append((channel, message))
        return 1


# --- SseFanoutManager ---


async def test_manager_delivers_to_all_user_queues():
    manager = SseFanoutManager()
    uid = uuid4()
    q1 = await manager.register(uid)
    q2 = await manager.register(uid)
    await manager.deliver(uid, "hello")
    assert q1.get_nowait() == "hello"
    assert q2.get_nowait() == "hello"


async def test_manager_unregister_removes_empty_bucket():
    manager = SseFanoutManager()
    uid = uuid4()
    queue = await manager.register(uid)
    await manager.unregister(uid, queue)
    await manager.deliver(uid, "dropped")  # 등록 없음 → no-op
    assert manager._by_user == {}


async def test_manager_drops_when_queue_full():
    manager = SseFanoutManager()
    uid = uuid4()
    queue = await manager.register(uid)
    for i in range(queue.maxsize):
        await manager.deliver(uid, str(i))
    await manager.deliver(uid, "overflow")  # 예외 없이 드롭
    assert queue.qsize() == queue.maxsize


# --- sse_subscribe ---


async def test_sse_subscribe_yields_delivered_payload_and_unregisters():
    uid = uuid4()
    stream = NotificationService.sse_subscribe(uid, heartbeat_interval_sec=5.0)
    task = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)  # register까지 진행
    await notification_sse_manager.deliver(uid, '{"k":1}')
    assert await task == 'data: {"k":1}\n\n'
    await stream.aclose()
    assert uid not in notification_sse_manager._by_user


async def test_sse_subscribe_emits_ping_on_idle():
    uid = uuid4()
    stream = NotificationService.sse_subscribe(uid, heartbeat_interval_sec=0.01)
    try:
        assert await anext(stream) == ": ping\n\n"
    finally:
        await stream.aclose()


# --- publish_after_commit 팬아웃 경로 ---


def _publish_kwargs(uid) -> dict[str, Any]:
    from app.common.enums import NotificationKind

    return {
        "recipient_user_id": uid,
        "notification_id": uuid4(),
        "kind": NotificationKind.LIKE_POST,
        "actor_id": None,
        "post_id": None,
        "comment_id": None,
    }


async def test_publish_after_commit_sends_single_channel_envelope():
    uid = uuid4()
    redis = _FakeRedis()
    await NotificationService.publish_after_commit(redis, **_publish_kwargs(uid))  # type: ignore[arg-type]
    [(channel, raw)] = redis.published
    assert channel == NOTIF_SSE_FANOUT_CHANNEL
    env = json.loads(raw)
    assert env["target_user_id"] == str(uid)
    assert json.loads(env["payload"])["kind"] == "LIKE_POST"


async def test_publish_after_commit_falls_back_to_local_on_redis_failure():
    uid = uuid4()
    queue = await notification_sse_manager.register(uid)
    try:
        await NotificationService.publish_after_commit(
            _FakeRedis(fail=True),  # type: ignore[arg-type]
            **_publish_kwargs(uid),
        )
        payload = queue.get_nowait()
        assert json.loads(payload)["kind"] == "LIKE_POST"
    finally:
        await notification_sse_manager.unregister(uid, queue)


async def test_publish_after_commit_delivers_locally_without_redis():
    uid = uuid4()
    queue = await notification_sse_manager.register(uid)
    try:
        await NotificationService.publish_after_commit(None, **_publish_kwargs(uid))
        assert queue.qsize() == 1
    finally:
        await notification_sse_manager.unregister(uid, queue)


# --- chat 폴백 (publish 성공 여부 신호) ---


async def test_chat_fanout_falls_back_locally_when_publish_fails(monkeypatch):
    sent: list[tuple[Any, str]] = []

    async def fake_send(user_id, message):
        sent.append((user_id, message))

    monkeypatch.setattr(
        "app.domain.chat.service.chat_connection_manager.send_personal_message", fake_send
    )
    peer, sender = uuid4(), uuid4()
    await ChatService._fanout_dm(_FakeRedis(fail=True), peer_id=peer, sender_id=sender, wire="w")  # type: ignore[arg-type]
    assert [(peer, "w"), (sender, "w")] == sent


async def test_chat_fanout_skips_local_when_publish_succeeds(monkeypatch):
    sent: list[Any] = []

    async def fake_send(user_id, message):
        sent.append(user_id)

    monkeypatch.setattr(
        "app.domain.chat.service.chat_connection_manager.send_personal_message", fake_send
    )
    redis = _FakeRedis()
    await ChatService._fanout_dm(redis, peer_id=uuid4(), sender_id=uuid4(), wire="w")  # type: ignore[arg-type]
    assert sent == []
    assert len(redis.published) == 2


async def test_publish_user_envelope_returns_false_without_redis():
    assert await publish_user_envelope(None, "ch", target_user_id=uuid4(), payload="p") is False


# --- 공용 리스너 채널 디스패치 ---


class _FakePubSub:
    def __init__(self, messages: list[dict[str, Any]], stop_event: asyncio.Event) -> None:
        self._messages = messages
        self._stop_event = stop_event
        self.closed = False

    async def subscribe(self, *channels: str) -> None:
        self.channels = channels

    async def unsubscribe(self, *channels: str) -> None:
        pass

    async def get_message(self, *, ignore_subscribe_messages: bool, timeout: float):
        if self._messages:
            return self._messages.pop(0)
        self._stop_event.set()
        return None

    async def aclose(self) -> None:
        self.closed = True


class _FakeListenerRedis:
    last: "_FakeListenerRedis | None" = None
    messages: list[dict[str, Any]] = []
    stop_event: asyncio.Event

    def __init__(self) -> None:
        self.pubsub_obj = _FakePubSub(list(self.messages), self.stop_event)
        type(self).last = self

    @classmethod
    def from_url(cls, url: str, decode_responses: bool = False) -> "_FakeListenerRedis":
        return cls()

    async def ping(self) -> bool:
        return True

    def pubsub(self) -> _FakePubSub:
        return self.pubsub_obj

    async def aclose(self) -> None:
        pass


async def test_listener_dispatches_by_channel(monkeypatch):
    stop_event = asyncio.Event()
    uid_chat, uid_notif = uuid4(), uuid4()
    _FakeListenerRedis.stop_event = stop_event
    _FakeListenerRedis.messages = [
        {
            "type": "message",
            "channel": "ch:chat",
            "data": json.dumps({"target_user_id": str(uid_chat), "payload": "dm"}),
        },
        {
            "type": "message",
            "channel": "ch:notif",
            "data": json.dumps({"target_user_id": str(uid_notif), "payload": "notif"}),
        },
        {"type": "message", "channel": "ch:unknown", "data": "ignored"},
        {"type": "message", "channel": "ch:chat", "data": "not-json"},  # envelope invalid → skip
    ]
    monkeypatch.setattr(pubsub_mod, "Redis", _FakeListenerRedis)

    received: dict[str, list[tuple[Any, str]]] = {"chat": [], "notif": []}

    async def chat_handler(user_id, payload):
        received["chat"].append((user_id, payload))

    async def notif_handler(user_id, payload):
        received["notif"].append((user_id, payload))

    await run_user_fanout_listener(
        redis_url="redis://test",
        handlers={"ch:chat": chat_handler, "ch:notif": notif_handler},
        stop_event=stop_event,
    )
    assert received["chat"] == [(uid_chat, "dm")]
    assert received["notif"] == [(uid_notif, "notif")]
    assert _FakeListenerRedis.last is not None
    assert _FakeListenerRedis.last.pubsub_obj.closed  # teardown 보장
