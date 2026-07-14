"""조회수 write-behind 버퍼링 단위 테스트.

실 Redis/DB 없이 FakeRedis + DB 쓰기 몽키패치로 핵심 불변식을 결정적으로 검증한다:
dedup(NX) · 버퍼 누적 · flush delta 반영 · 실패 시 drain 재병합 · 락 해제 CAS(남의 락 미삭제).
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.core.config import settings
from app.domain.posts.services import post_service as ps

from tests.unit.fakes import FakeDB, FakeRedis, RecordingDB, as_session

pytestmark = pytest.mark.asyncio


class _FakeConn:
    async def __aenter__(self):
        return FakeDB()

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


async def test_dedup_blocks_repeat_viewer(monkeypatch):
    """같은 viewer_key는 TTL 창 안에서 두 번째부터 조회수 증가를 막는다(SET NX)."""
    monkeypatch.setattr(
        settings, "VIEW_CACHE_TTL_SECONDS", 3600
    )  # 환경(.env TTL 0) 무관하게 dedup 켬
    r = FakeRedis()
    pid = uuid.uuid4()
    assert await ps._consume_view_if_new_redis(pid, "u:1", r) is True
    assert await ps._consume_view_if_new_redis(pid, "u:1", r) is False
    # 다른 viewer는 독립적으로 허용
    assert await ps._consume_view_if_new_redis(pid, "u:2", r) is True


async def test_dedup_disabled_when_ttl_zero(monkeypatch):
    """TTL 0 = dedup 끔(compose 로컬 편의 의도) — 같은 viewer의 반복 조회도 매번 집계."""
    monkeypatch.setattr(settings, "VIEW_CACHE_TTL_SECONDS", 0)
    r = FakeRedis()
    pid = uuid.uuid4()
    assert await ps._consume_view_if_new_redis(pid, "u:1", r) is True
    assert await ps._consume_view_if_new_redis(pid, "u:1", r) is True
    assert r.kv == {}  # dedup 키를 만들지 않는다(Redis 무접촉)


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


# ---- 조회수 증가 안무(_apply_view_increment) + GET 상세 경로 ----


def _fake_post(pid: uuid.UUID, view_count: int = 0):
    """PostResponse.model_validate(from_attributes)가 통과하는 최소 게시글 객체."""
    return SimpleNamespace(
        id=pid,
        title="t",
        content="c",
        view_count=view_count,
        like_count=0,
        comment_count=0,
        author=None,
        files=[],
        category_id=None,
        hashtags=[],
        version=1,
        created_at=datetime.now(UTC),
    )


def _patch_detail_load(monkeypatch, post):
    async def _load(cls, post_id, *, db, current_user_id=None):
        return post

    monkeypatch.setattr(ps.PostsModel, "get_post_by_id", classmethod(_load))


async def test_apply_view_increment_contract(monkeypatch):
    """안무 계약: dedup 차단→False, 버퍼 흡수→False(DB 무접촉), 버퍼 실패→True(writer 직접)."""
    monkeypatch.setattr(
        settings, "VIEW_CACHE_TTL_SECONDS", 3600
    )  # 환경(.env TTL 0) 무관하게 dedup 켬
    r = FakeRedis()
    pid = uuid.uuid4()
    incremented: list[uuid.UUID] = []

    async def _inc(cls, post_id, db):
        incremented.append(post_id)
        return True

    monkeypatch.setattr(ps.PostsModel, "increment_view_count", classmethod(_inc))

    writer = RecordingDB()
    # 첫 조회: 버퍼가 흡수 → DB 직접 증가 없음(False)
    assert await ps._apply_view_increment(pid, "u:1", r, as_session(writer)) is False
    assert await ps._get_buffer_pending(r, pid) == 1
    # 같은 viewer 재조회: dedup 차단 → 버퍼도 DB도 무접촉(False)
    assert await ps._apply_view_increment(pid, "u:1", r, as_session(writer)) is False
    assert await ps._get_buffer_pending(r, pid) == 1
    assert writer.begin_count == 0 and incremented == []
    # Redis 불능: dedup fail-open + 버퍼 실패 → writer 직접 증가(True)
    assert await ps._apply_view_increment(pid, "u:2", None, as_session(writer)) is True
    assert incremented == [pid]
    assert writer.begin_count == 1


async def test_get_post_detail_raises_when_not_found(monkeypatch):
    from app.common.exceptions import PostNotFoundException

    _patch_detail_load(monkeypatch, None)
    with pytest.raises(PostNotFoundException):
        await ps.PostService.get_post_detail(
            uuid.uuid4(),
            as_session(RecordingDB()),
            viewer_key="u:1",
            redis_client=FakeRedis(),
            writer_db=as_session(RecordingDB()),
        )


async def test_get_post_detail_falls_back_to_writer_and_reflects_increment(monkeypatch):
    """Redis 버퍼 실패(fail-open) 시 writer 세션으로 직접 increment하고,
    그 증가분(extra_db)이 응답 view_count에 즉시 반영된다."""
    pid = uuid.uuid4()
    _patch_detail_load(monkeypatch, _fake_post(pid, view_count=10))
    incremented: list[tuple[uuid.UUID, object]] = []

    async def _inc(cls, post_id, db):
        incremented.append((post_id, db))
        return True

    monkeypatch.setattr(ps.PostsModel, "increment_view_count", classmethod(_inc))

    reader, writer = RecordingDB(), RecordingDB()
    data = await ps.PostService.get_post_detail(
        pid, as_session(reader), viewer_key="u:1", redis_client=None, writer_db=as_session(writer)
    )

    assert incremented == [(pid, writer)]  # 폴백 쓰기는 반드시 writer로
    assert writer.begin_count == 1
    assert data.view_count == 11  # DB 직접 증가분이 응답에 즉시 반영


async def test_get_post_detail_reflects_buffer_pending(monkeypatch):
    """버퍼에 흡수된 증가분은 DB에 없지만 응답 view_count에는 pending으로 반영된다."""
    r = FakeRedis()
    pid = uuid.uuid4()
    _patch_detail_load(monkeypatch, _fake_post(pid, view_count=10))

    reader, writer = RecordingDB(), RecordingDB()
    data = await ps.PostService.get_post_detail(
        pid, as_session(reader), viewer_key="u:1", redis_client=r, writer_db=as_session(writer)
    )

    assert await ps._get_buffer_pending(r, pid) == 1
    assert writer.begin_count == 0  # 버퍼가 흡수 — writer 무접촉
    assert data.view_count == 11  # base 10 + pending 1
