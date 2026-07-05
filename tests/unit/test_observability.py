"""관측성(ADR 0006) — DB/Redis 없이 검증하는 probe·metrics 회귀 테스트.

httpx.ASGITransport는 lifespan을 실행하지 않아 외부 PG/Redis 없이 라우트·미들웨어를 태운다.
readyz의 DB 게이트는 app.main.check_database를 패치해 검증한다.
"""

import asyncio
from unittest.mock import patch

import app.main as main
import httpx


def _run(coro):
    return asyncio.run(coro)


async def _get(path: str, *, hits: tuple[str, ...] = ()) -> httpx.Response:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        for h in hits:
            await c.get(h)
        return await c.get(path)


def test_livez_is_dependency_free():
    # liveness는 의존성 체크 없이 항상 alive — DB/Redis 미기동이어도 200.
    r = _run(_get("/livez"))
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_readyz_gates_on_db_hard_redis_soft():
    async def db_up() -> bool:
        return True

    async def db_down() -> bool:
        return False

    # DB up → ready. Redis 미연결(soft)이라 down으로 report만 하고 게이트하지 않는다.
    with patch.object(main, "check_database", db_up):
        r = _run(_get("/readyz"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["db"] == "ok"
    assert body["redis"] == "down"  # soft — 200을 막지 않음

    # DB down → not_ready(503). DB가 유일한 hard 의존성.
    with patch.object(main, "check_database", db_down):
        r2 = _run(_get("/readyz"))
    assert r2.status_code == 503
    assert r2.json()["status"] == "not_ready"
    assert r2.json()["db"] == "down"


def test_metrics_exposes_red_and_excludes_probes():
    # "/" 요청은 기록(라우트 템플릿 라벨), /livez는 skip 대상이라 기록 안 됨.
    r = _run(_get("/metrics", hits=("/", "/livez")))
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "http_requests_in_progress" in body
    # 라우트 템플릿 라벨: "/"는 기록, probe(/livez)·/metrics는 제외.
    assert 'path="/"' in body
    assert "/livez" not in body
    assert 'path="/metrics"' not in body
