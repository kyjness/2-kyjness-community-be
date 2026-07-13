"""RateLimit 미들웨어 배치·redis 탐색 단위 테스트 (실 Redis 없이 FakeRedis).

검증 불변식:
- redis 탐색은 scope["app"] 기반으로 동작한다(체인 .app 순회는 항상 None이 나오는 결함이었다).
- 429는 CORS·RED 메트릭·X-Request-ID를 "거쳐" 나간다 — RateLimit이 최안쪽이어야 성립.
"""

import pytest
from app.core.config import settings
from app.core.middleware.metrics import REQUESTS_TOTAL
from app.main import app
from starlette.testclient import TestClient

_UNMATCHED = "__unmatched__"


class FakeRedis:
    """rate limit Lua(INCR+EXPIRE+TTL)만 흉내내는 인메모리 가짜."""

    def __init__(self) -> None:
        self.eval_calls = 0
        self.counts: dict[str, int] = {}

    async def eval(self, script, numkeys, key, window):
        self.eval_calls += 1
        c = self.counts.get(key, 0) + 1
        self.counts[key] = c
        return [c, int(window)]


@pytest.fixture()
def client(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(app.state, "redis", fake, raising=False)
    with_client = TestClient(app)  # lifespan 미실행(DB/Redis 실연결 없음)
    yield with_client, fake
    # monkeypatch가 app.state.redis를 원복한다.


def _429_counter_value() -> float:
    return REQUESTS_TOTAL.labels(method="GET", path=_UNMATCHED, status=429)._value.get()


def test_redis_discovered_via_scope_and_429_passes_observability(client, monkeypatch):
    tc, fake = client
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_REQUESTS", 1)
    origin = settings.CORS_ORIGINS[0]
    before = _429_counter_value()

    ok = tc.get("/v1/", headers={"Origin": origin})
    assert ok.status_code == 200

    limited = tc.get("/v1/", headers={"Origin": origin})
    assert limited.status_code == 429

    # scope["app"] 기반 탐색이 동작해 Redis 경로(fixed window Lua)를 탔다.
    assert fake.eval_calls == 2

    # CORS 안쪽에서 429가 생성되어 브라우저가 응답을 읽을 수 있다.
    assert limited.headers.get("access-control-allow-origin") == origin
    assert "retry-after" in limited.headers

    # RequestId(최외곽)가 429에도 적용된다 — 헤더·바디 상관.
    assert limited.headers.get("x-request-id")
    assert limited.json()["requestId"] == limited.headers["x-request-id"]

    # RED 메트릭에 429가 집계된다(라우트 매칭 전이라 path=__unmatched__).
    assert _429_counter_value() == before + 1


def test_options_and_probe_paths_skip_rate_limit(client, monkeypatch):
    tc, fake = client
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_REQUESTS", 1)

    # probe 경로는 카운트 자체가 없다.
    assert tc.get("/livez").status_code == 200
    assert fake.eval_calls == 0
