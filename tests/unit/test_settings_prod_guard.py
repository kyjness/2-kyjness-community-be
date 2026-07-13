"""프로덕션 설정 가드 단위 테스트.

핵심 불변식: 운영 전제(ALB/Nginx 뒤)에서 프록시 신뢰(XFF)가 꺼져 있으면 기동을 막는다 —
IP 기반 rate limit·조회수 dedup이 소수 프록시 IP로 수렴해 전역 429 자기-DoS가 되는 설정 결함을
배포 전에 fail-fast로 잡는다.
"""

import pytest
from app.core.config import settings, validate_settings_for_environment


def _make_prod_valid(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "TRUSTED_HOSTS", ["api.puppytalk.shop"])
    monkeypatch.setattr(settings, "DB_PASSWORD", "pw")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://puppytalk.shop"])
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "bucket")
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(settings, "TRUST_X_FORWARDED_FOR", True)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", ["10.0.0.0/8"])


def test_prod_guard_passes_with_proxy_trust(monkeypatch):
    _make_prod_valid(monkeypatch)
    validate_settings_for_environment()  # 예외 없음


def test_prod_guard_rejects_missing_proxy_trust(monkeypatch):
    _make_prod_valid(monkeypatch)
    monkeypatch.setattr(settings, "TRUST_X_FORWARDED_FOR", False)
    with pytest.raises(ValueError, match="TRUST_X_FORWARDED_FOR"):
        validate_settings_for_environment()


def test_prod_guard_rejects_empty_proxy_ranges(monkeypatch):
    _make_prod_valid(monkeypatch)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", [])
    with pytest.raises(ValueError, match="TRUSTED_PROXY_IPS"):
        validate_settings_for_environment()


def test_dev_environment_skips_guard(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "TRUST_X_FORWARDED_FOR", False)
    validate_settings_for_environment()  # 개발 환경은 가드 미적용
