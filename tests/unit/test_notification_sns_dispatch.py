"""알림 SNS 배송 오프로드 단위 테스트.

실 브로커/SNS 없이 몽키패치로 라우팅 불변식을 검증한다:
CELERY_ENABLED=true → 태스크 enqueue(결정적 멱등키) · enqueue 실패/비활성 → 인라인 폴백 ·
워커 잡은 publish 성공 후에만 멱등 마킹(실패 재시도가 skip으로 유실되지 않음).
"""

import uuid

import pytest
from app.common.enums import NotificationKind
from app.core.config import settings
from app.core.ids import uuid_to_base62
from app.domain.notifications.service import NotificationService
from app.worker.jobs import notification_delivery as job

pytestmark = pytest.mark.asyncio

_KIND = NotificationKind.COMMENT_ON_POST


def _ids():
    return uuid.uuid4(), uuid.uuid4()


class _RecordingTask:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self._fail = fail

    def delay(self, **kwargs):
        if self._fail:
            raise ConnectionError("broker down")
        self.calls.append(kwargs)


async def _dispatch(recipient, nid):
    await NotificationService._dispatch_sns_publish(
        recipient_user_id=recipient,
        notification_id=nid,
        kind=_KIND,
        actor_id=None,
        post_id=None,
        comment_id=None,
    )


async def test_dispatch_enqueues_celery_task_when_enabled(monkeypatch):
    recipient, nid = _ids()
    task = _RecordingTask()
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "arn:aws:sns:test:topic")
    monkeypatch.setattr(settings, "CELERY_ENABLED", True)
    import app.worker.tasks.notifications as tasks_mod

    monkeypatch.setattr(tasks_mod, "deliver_notification_sns", task)

    inline_calls: list[dict] = []
    monkeypatch.setattr(
        NotificationService,
        "_schedule_sns_publish",
        classmethod(lambda cls, **kw: inline_calls.append(kw)),
    )

    await _dispatch(recipient, nid)

    assert len(task.calls) == 1
    call = task.calls[0]
    assert call["notification_id"] == uuid_to_base62(nid)
    assert call["user_id"] == uuid_to_base62(recipient)
    # 결정적 멱등키: 같은 알림의 중복 enqueue가 워커에서 1회 배송으로 수렴해야 한다.
    assert call["idempotency_key"] == f"sns:{uuid_to_base62(nid)}"
    assert inline_calls == []


async def test_dispatch_falls_back_inline_when_enqueue_fails(monkeypatch):
    recipient, nid = _ids()
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "arn:aws:sns:test:topic")
    monkeypatch.setattr(settings, "CELERY_ENABLED", True)
    import app.worker.tasks.notifications as tasks_mod

    monkeypatch.setattr(tasks_mod, "deliver_notification_sns", _RecordingTask(fail=True))

    inline_calls: list[dict] = []
    monkeypatch.setattr(
        NotificationService,
        "_schedule_sns_publish",
        classmethod(lambda cls, **kw: inline_calls.append(kw)),
    )

    await _dispatch(recipient, nid)
    assert len(inline_calls) == 1


async def test_dispatch_uses_inline_when_celery_disabled(monkeypatch):
    recipient, nid = _ids()
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "arn:aws:sns:test:topic")
    monkeypatch.setattr(settings, "CELERY_ENABLED", False)

    inline_calls: list[dict] = []
    monkeypatch.setattr(
        NotificationService,
        "_schedule_sns_publish",
        classmethod(lambda cls, **kw: inline_calls.append(kw)),
    )

    await _dispatch(recipient, nid)
    assert len(inline_calls) == 1


async def test_dispatch_noop_without_topic(monkeypatch):
    recipient, nid = _ids()
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "")
    monkeypatch.setattr(settings, "CELERY_ENABLED", True)

    inline_calls: list[dict] = []
    monkeypatch.setattr(
        NotificationService,
        "_schedule_sns_publish",
        classmethod(lambda cls, **kw: inline_calls.append(kw)),
    )

    await _dispatch(recipient, nid)
    assert inline_calls == []


# ---- 워커 잡: 멱등 마킹 순서 ----


class _FakeRedisClient:
    def __init__(self, preloaded: dict[str, str] | None = None) -> None:
        self.kv = dict(preloaded or {})
        self.set_calls: list[str] = []

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, val, ex=None):
        self.kv[key] = val
        self.set_calls.append(key)
        return True

    async def aclose(self):
        pass


class _FakeRedisFactory:
    """job 모듈의 `Redis` 이름을 대체 — from_url이 준비된 fake 클라이언트를 반환."""

    def __init__(self, client: _FakeRedisClient) -> None:
        self._client = client

    def from_url(self, *_a, **_kw):
        return self._client


class _FakeRow:
    def __init__(self, nid, uid) -> None:
        self.id = nid
        self.user_id = uid
        self.kind = _KIND.value
        self.actor_id = None
        self.post_id = None
        self.comment_id = None


def _patch_job_db(monkeypatch, row):
    from contextlib import asynccontextmanager

    class _FakeTx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class _FakeDb:
        def begin(self):
            return _FakeTx()

    @asynccontextmanager
    async def _fake_conn():
        yield _FakeDb()

    async def _fake_load(db, *, notification_id, user_id):
        return row

    monkeypatch.setattr(job, "get_connection", _fake_conn)
    monkeypatch.setattr(job, "_load_notification", _fake_load)


async def test_job_marks_idempotent_only_after_publish_success(monkeypatch):
    uid, nid = _ids()
    client = _FakeRedisClient()
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "arn:aws:sns:test:topic")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake:6379/0")
    monkeypatch.setattr(job, "Redis", _FakeRedisFactory(client))
    _patch_job_db(monkeypatch, _FakeRow(nid, uid))

    published: list[str] = []
    monkeypatch.setattr(job, "_sns_publish_sync", lambda topic, msg: published.append(msg))

    out = await job.deliver_notification_sns_async(
        notification_id=str(nid), user_id=str(uid), idempotency_key="sns:test-key"
    )
    assert out["status"] == "delivered"
    assert len(published) == 1
    assert client.set_calls == [f"{job._IDEMP_KEY_PREFIX}sns:test-key"]


async def test_job_does_not_mark_idempotent_when_publish_fails(monkeypatch):
    uid, nid = _ids()
    client = _FakeRedisClient()
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "arn:aws:sns:test:topic")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake:6379/0")
    monkeypatch.setattr(job, "Redis", _FakeRedisFactory(client))
    _patch_job_db(monkeypatch, _FakeRow(nid, uid))

    def _boom(topic, msg):
        raise ConnectionError("sns down")

    monkeypatch.setattr(job, "_sns_publish_sync", _boom)

    with pytest.raises(ConnectionError):
        await job.deliver_notification_sns_async(
            notification_id=str(nid), user_id=str(uid), idempotency_key="sns:test-key"
        )
    # 마킹이 없어야 Celery 재시도가 멱등 skip으로 유실되지 않는다.
    assert client.set_calls == []


async def test_job_skips_when_already_delivered(monkeypatch):
    uid, nid = _ids()
    client = _FakeRedisClient(preloaded={f"{job._IDEMP_KEY_PREFIX}sns:test-key": "1"})
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "arn:aws:sns:test:topic")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake:6379/0")
    monkeypatch.setattr(job, "Redis", _FakeRedisFactory(client))

    published: list[str] = []
    monkeypatch.setattr(job, "_sns_publish_sync", lambda topic, msg: published.append(msg))

    out = await job.deliver_notification_sns_async(
        notification_id=str(nid), user_id=str(uid), idempotency_key="sns:test-key"
    )
    assert out == {"status": "skipped", "reason": "idempotent"}
    assert published == []
