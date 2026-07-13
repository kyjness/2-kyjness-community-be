"""미들웨어 경로 상수 드리프트 가드.

rate limit 미들웨어는 라우팅 전에 경로 문자열로 전용 한도를 판별한다 — 라우트가
개명되면 전용 한도가 조용히 글로벌로 강등되므로, 상수가 실제 등록 경로와 일치함을
앱 라우트 테이블과 대조해 고정한다.
"""

from app.common.paths import (
    HEALTH_PATH,
    LOGIN_PATH,
    SIGNUP_CONFIRM_PATH,
    SIGNUP_PRESIGN_PATH,
)
from app.main import app


def test_middleware_path_constants_match_registered_routes():
    registered = {getattr(r, "path", None) for r in app.routes}
    for const in (LOGIN_PATH, SIGNUP_PRESIGN_PATH, SIGNUP_CONFIRM_PATH, HEALTH_PATH):
        assert const in registered, f"미들웨어 경로 상수가 등록 라우트에 없음: {const}"


def test_probe_paths_registered_at_app_root():
    """_SKIP_PATHS의 루트 프로브(/livez·/readyz·/metrics)도 실경로와 일치해야 한다."""
    registered = {getattr(r, "path", None) for r in app.routes}
    for probe in ("/livez", "/readyz", "/metrics"):
        assert probe in registered
