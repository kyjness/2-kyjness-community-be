# Prometheus RED 메트릭. access_log와 동형 @app.middleware("http")로 요청 수·지연·in-flight 측정.
import time
from collections.abc import Awaitable, Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

# 라벨 path는 raw URL이 아니라 라우트 템플릿(/v1/posts/{post_id})을 쓴다 — 경로 파라미터가
# 값마다 새 시계열을 만드는 카디널리티 폭증을 막는다. probe·/metrics 자신은 기록에서 제외.
_UNMATCHED = "__unmatched__"
_SKIP_PATHS = frozenset({"/metrics", "/livez", "/readyz"})

REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP 요청 총계",
    ["method", "path", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP 요청 처리 시간(초)",
    ["method", "path"],
)
IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "처리 중인 HTTP 요청 수(in-flight)",
    ["method", "path"],
)


def _route_template(request: Request) -> str | None:
    """매칭된 라우트의 경로 템플릿. call_next 이후 scope["route"]가 채워진다."""
    route = request.scope.get("route")
    return getattr(route, "path", None)


async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    # 라우트 매칭 전이라 skip 판정은 raw path로, 라벨은 매칭 후 템플릿으로.
    if request.url.path in _SKIP_PATHS:
        return await call_next(request)

    method = request.method
    start = time.perf_counter()
    # in-flight는 라우트 템플릿을 아직 모르므로 미매칭 라벨로 잡고, 완료 시 정확한 라벨로 계측한다.
    pending = IN_PROGRESS.labels(method=method, path=_UNMATCHED)
    pending.inc()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        pending.dec()
        path = _route_template(request) or _UNMATCHED
        REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        REQUEST_DURATION.labels(method=method, path=path).observe(duration)


def render_metrics() -> tuple[bytes, str]:
    """/metrics 노출용 (본문, content-type)."""
    return generate_latest(), CONTENT_TYPE_LATEST
