"""조회수 write-behind 버퍼링 단위 테스트.

실 Redis/DB 없이 FakeRedis + DB 쓰기 몽키패치로 핵심 불변식을 결정적으로 검증한다:
dedup(NX) · 버퍼 누적 · flush delta 반영 · 실패 시 drain 재병합 · 락 해제 CAS(남의 락 미삭제).
"""

import uuid
from typing import cast

import pytest
from app.domain.posts.services import post_service as ps
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


class FakeRedis:
    """post_service가 쓰는 명령만 구현한 인메모리 가짜. eval은 실제 Lua 2종을 흉내낸다."""

    def __init__(self, fail_delete_substr: str | None = None) -> None:
        self.kv: dict[str, str] = {}
        self.hashes: dict[str, dict[str, int]] = {}
        self._fail_delete_substr = fail_delete_substr

    async def set(self, key, val, nx=False, ex=None):
        if nx and key in self.kv:
            return None
        self.kv[key] = val
        return True

    async def get(self, key):
        v = self.kv.get(key)
        return v.encode() if v is not None else None

    async def delete(self, key):
        if self._fail_delete_substr is not None and self._fail_delete_substr in key:
            raise ConnectionError("redis del failed")
        existed = key in self.kv or key in self.hashes
        self.kv.pop(key, None)
        self.hashes.pop(key, None)
        return 1 if existed else 0

    @staticmethod
    def _field(field):
        # 실 Redis처럼 bytes 필드와 str 필드를 동일 키로 취급.
        return field.decode() if isinstance(field, (bytes, bytearray)) else field

    async def hincrby(self, key, field, n):
        h = self.hashes.setdefault(key, {})
        f = self._field(field)
        h[f] = h.get(f, 0) + n
        return h[f]

    async def hget(self, key, field):
        v = self.hashes.get(key, {}).get(self._field(field))
        return str(v).encode() if v is not None else None

    async def hgetall(self, key):
        h = self.hashes.get(key, {})
        return {k.encode(): str(v).encode() for k, v in h.items()}

    async def eval(self, script, numkeys, *args):
        keys = args[:numkeys]
        argv = args[numkeys:]
        if "RENAME" in script:  # buffer -> drain (원자 스왑)
            src, dst = keys[0], keys[1]
            if not self.hashes.get(src):
                return 0
            self.hashes[dst] = self.hashes.pop(src)
            return 1
        # CAS 해제: GET==ARGV[0] 일 때만 DEL
        k, expected = keys[0], argv[0]
        if self.kv.get(k) == expected:
            self.kv.pop(k, None)
            return 1
        return 0


class _FakeBegin:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        return False


class _FakeDB:
    def begin(self):
        return _FakeBegin()


class _FakeConn:
    async def __aenter__(self):
        return _FakeDB()

    async def __aexit__(self, *a):
        return False


def _fake_get_connection():
    return _FakeConn()


def _patch_db(monkeypatch, on_delta):
    """flush_view_counts_to_db의 DB 쓰기 경로를 가로챈다."""

    async def _delta(cls, post_id, delta, db):
        return await on_delta(post_id, delta)

    monkeypatch.setattr(ps.PostsModel, "increment_view_count_delta", classmethod(_delta))
    monkeypatch.setattr("app.db.session.get_connection", _fake_get_connection)


async def test_dedup_blocks_repeat_viewer():
    """같은 viewer_key는 TTL 창 안에서 두 번째부터 조회수 증가를 막는다(SET NX)."""
    r = FakeRedis()
    pid = uuid.uuid4()
    assert await ps._consume_view_if_new_redis(pid, "u:1", r) is True
    assert await ps._consume_view_if_new_redis(pid, "u:1", r) is False
    # 다른 viewer는 독립적으로 허용
    assert await ps._consume_view_if_new_redis(pid, "u:2", r) is True


async def test_buffer_accumulates_pending():
    r = FakeRedis()
    pid = uuid.uuid4()
    assert await ps._try_view_increment_in_buffer(pid, r) is True
    assert await ps._try_view_increment_in_buffer(pid, r) is True
    assert await ps._get_buffer_pending(r, pid) == 2


async def test_buffer_increment_fails_open_when_redis_down():
    """redis_client None이면 버퍼 증가는 False(→ 호출부가 DB 직접 증가로 폴백)."""
    pid = uuid.uuid4()
    assert await ps._try_view_increment_in_buffer(pid, None) is False


async def test_flush_applies_deltas_and_releases_lock(monkeypatch):
    r = FakeRedis()
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    await ps._try_view_increment_in_buffer(p1, r)
    await ps._try_view_increment_in_buffer(p1, r)  # p1 = 2
    await ps._try_view_increment_in_buffer(p2, r)  # p2 = 1

    recorded: dict[uuid.UUID, int] = {}

    async def on_delta(post_id, delta):
        recorded[post_id] = delta
        return True

    _patch_db(monkeypatch, on_delta)
    flushed_before = ps.VIEW_BUFFER_FLUSHED_VIEWS._value.get()
    await ps.PostService.flush_view_counts_to_db(r)

    assert recorded == {p1: 2, p2: 1}
    assert await ps._get_buffer_pending(r, p1) == 0  # 버퍼 비워짐
    assert await ps._get_buffer_pending(r, p2) == 0
    assert ps.VIEW_FLUSH_LOCK_KEY not in r.kv  # 자기 락 해제됨
    # 커밋된 view 합(p1 2 + p2 1)이 메트릭에 반영됐다.
    assert ps.VIEW_BUFFER_FLUSHED_VIEWS._value.get() - flushed_before == 3


async def test_flush_noop_when_lock_held():
    """다른 워커가 락을 보유 중이면 flush는 아무 것도 하지 않고 즉시 반환."""
    r = FakeRedis()
    p1 = uuid.uuid4()
    await ps._try_view_increment_in_buffer(p1, r)
    r.kv[ps.VIEW_FLUSH_LOCK_KEY] = "other-worker"  # 선점

    await ps.PostService.flush_view_counts_to_db(r)

    # 버퍼는 그대로 남고, 남의 락도 건드리지 않는다.
    assert await ps._get_buffer_pending(r, p1) == 1
    assert r.kv.get(ps.VIEW_FLUSH_LOCK_KEY) == "other-worker"


async def test_flush_merges_back_on_db_error(monkeypatch):
    """flush 중 DB 오류면 drain을 버퍼로 되돌리고(유실 방지) 예외를 올린다."""
    r = FakeRedis()
    p1 = uuid.uuid4()
    await ps._try_view_increment_in_buffer(p1, r)
    await ps._try_view_increment_in_buffer(p1, r)  # 2

    async def boom(post_id, delta):
        raise RuntimeError("db down")

    _patch_db(monkeypatch, boom)
    with pytest.raises(RuntimeError):
        await ps.PostService.flush_view_counts_to_db(r)

    assert await ps._get_buffer_pending(r, p1) == 2  # 재병합됨
    assert ps.VIEW_FLUSH_LOCK_KEY not in r.kv  # finally에서 자기 락 해제


async def test_flush_no_double_count_when_drain_delete_fails(monkeypatch):
    """커밋 성공 후 drain 삭제만 실패해도 재병합하지 않는다(이미 반영된 delta 이중 집계 방지)."""
    r = FakeRedis(fail_delete_substr=":drain:")
    p1 = uuid.uuid4()
    await ps._try_view_increment_in_buffer(p1, r)
    await ps._try_view_increment_in_buffer(p1, r)  # 2

    calls: list[int] = []

    async def on_delta(post_id, delta):
        calls.append(delta)
        return True

    _patch_db(monkeypatch, on_delta)
    # drain 삭제가 실패해도 예외를 삼키고 정상 종료해야 한다.
    await ps.PostService.flush_view_counts_to_db(r)

    assert calls == [2]  # delta는 정확히 한 번만 반영
    assert await ps._get_buffer_pending(r, p1) == 0  # 버퍼로 되돌리지 않음(이중 집계 없음)
    assert ps.VIEW_FLUSH_LOCK_KEY not in r.kv  # 락은 정상 해제


async def test_flush_does_not_release_foreign_lock(monkeypatch):
    """락 TTL 만료 후 다른 워커가 재획득한 상황: 우리 finally의 CAS는 남의 락을 지우면 안 된다(#2)."""
    r = FakeRedis()
    p1 = uuid.uuid4()
    await ps._try_view_increment_in_buffer(p1, r)

    async def steal_then_write(post_id, delta):
        # 우리가 DB에 쓰는 사이 락이 만료돼 다른 워커가 재획득한 상황 재현
        r.kv[ps.VIEW_FLUSH_LOCK_KEY] = "other-worker"
        return True

    _patch_db(monkeypatch, steal_then_write)
    await ps.PostService.flush_view_counts_to_db(r)

    # 값이 다르므로 CAS DEL은 0을 반환하고 남의 락은 살아 있어야 한다.
    assert r.kv.get(ps.VIEW_FLUSH_LOCK_KEY) == "other-worker"


# ---- record_post_view 핫패스 (#29) ----


class _RecordingDB(_FakeDB):
    """begin() 호출 수를 세는 가짜 세션 — writer 트랜잭션이 열렸는지 판별용."""

    def __init__(self) -> None:
        self.begin_count = 0

    def begin(self):
        self.begin_count += 1
        return _FakeBegin()


def _sess(db) -> AsyncSession:
    """가짜 세션을 시그니처 타입에 맞춰 전달(런타임은 begin()만 쓴다)."""
    return cast(AsyncSession, db)


def _patch_visibility(monkeypatch, visible: bool, calls: list | None = None):
    async def _visible(cls, post_id, *, db, current_user_id=None):
        if calls is not None:
            calls.append(post_id)
        return visible

    monkeypatch.setattr(ps.PostsModel, "post_is_visible", classmethod(_visible))


async def test_record_view_checks_visibility_without_full_load(monkeypatch):
    """가시성은 EXISTS(post_is_visible)로만 확인 — 상세 eager-load 경로를 타면 실패."""
    r = FakeRedis()
    pid = uuid.uuid4()
    seen: list[uuid.UUID] = []
    _patch_visibility(monkeypatch, True, seen)

    async def _forbidden_full_load(cls, *a, **kw):
        raise AssertionError(
            "record_post_view는 get_post_by_id(상세 eager-load)를 호출하면 안 된다"
        )

    monkeypatch.setattr(ps.PostsModel, "get_post_by_id", classmethod(_forbidden_full_load))

    reader, writer = _RecordingDB(), _RecordingDB()
    await ps.PostService.record_post_view(
        pid, "u:1", _sess(reader), redis_client=r, writer_db=_sess(writer)
    )

    assert seen == [pid]
    assert await ps._get_buffer_pending(r, pid) == 1
    # Redis 버퍼가 흡수했으므로 writer 트랜잭션은 열리지 않는다(reader만 사용).
    assert writer.begin_count == 0
    assert reader.begin_count == 1


async def test_record_view_raises_when_not_visible(monkeypatch):
    from app.common.exceptions import PostNotFoundException

    _patch_visibility(monkeypatch, False)
    with pytest.raises(PostNotFoundException):
        await ps.PostService.record_post_view(
            uuid.uuid4(),
            "u:1",
            _sess(_RecordingDB()),
            redis_client=FakeRedis(),
            writer_db=_sess(_RecordingDB()),
        )


async def test_record_view_falls_back_to_writer_when_buffer_unavailable(monkeypatch):
    """Redis 버퍼 실패(fail-open) 시에만 writer 세션으로 직접 increment."""
    pid = uuid.uuid4()
    _patch_visibility(monkeypatch, True)
    incremented: list[tuple[uuid.UUID, object]] = []

    async def _inc(cls, post_id, db):
        incremented.append((post_id, db))
        return True

    monkeypatch.setattr(ps.PostsModel, "increment_view_count", classmethod(_inc))

    reader, writer = _RecordingDB(), _RecordingDB()
    await ps.PostService.record_post_view(
        pid, "u:1", _sess(reader), redis_client=None, writer_db=_sess(writer)
    )

    assert incremented == [(pid, writer)]  # 폴백 쓰기는 반드시 writer로
    assert writer.begin_count == 1
