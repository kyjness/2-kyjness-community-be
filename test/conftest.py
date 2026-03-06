import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENV", "development")

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/v1/auth/signup",
        json={"email": email, "password": password, "nickname": email.split("@")[0][:20]},
    )
    res = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return {"session_id": res.cookies.get("session_id")}


@pytest.fixture(scope="module")
def auth_cookies(client):
    """인증된 사용자 쿠키 (테스트용 고정 이메일)."""
    return _login(client, "auth_user@example.com", "password12")
