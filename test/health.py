def test_root(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "OK"
    assert "data" in data
    assert data["data"]["message"] == "PuppyTalk API is running!"


def test_health(client):
    res = client.get("/health")
    data = res.json()
    assert res.status_code in (200, 503)
    assert "status" in data["data"]
    if res.status_code == 200:
        assert data["code"] == "OK"
        assert data["data"]["status"] == "ok"
        assert data["data"].get("database") == "connected"
    else:
        assert res.status_code == 503
        assert data["code"] == "DB_ERROR"
        assert data["data"].get("database") == "disconnected"
