# 도메인(서비스 계층) Prometheus 메트릭. 운영 봉투 가정을 /metrics로 실측한다(ADR 0006).
# http RED 지표는 전송 계층이라 middleware/metrics.py에 둔다. 여기 카운터는 default registry에
# 등록돼 같은 /metrics로 함께 노출된다.
from prometheus_client import Counter

# rate limit 429 — 어떤 한도(login·signup_upload·global)가 압력을 받는지.
RATE_LIMIT_REJECTIONS = Counter(
    "rate_limit_rejections_total",
    "Rate limit으로 429 반려된 요청 수",
    ["limit"],
)

# 캐시 hit/miss — 읽기 폭주 경로 캐시가 실제로 얼마나 먹히는지(hit ratio).
CACHE_EVENTS = Counter(
    "cache_events_total",
    "캐시 조회 결과(hit/miss)",
    ["cache", "result"],
)

# 조회수 write-behind — flush로 DB에 반영된 view 합(조회 폭주 가정의 실측 throughput).
VIEW_BUFFER_FLUSHED_VIEWS = Counter(
    "view_buffer_flushed_views_total",
    "조회수 버퍼 flush로 DB에 반영된 view 총합",
)
