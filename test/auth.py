def test_signup_success(client):
    res = client.post(
        "/v1/auth/signup",
        json={
            "email": "signup_ok@example.com",
            "password": "password12",
            "nickname": "signupuser",
        },
    )
    assert res.status_code == 201
    assert res.json()["code"] == "SIGNUP_SUCCESS"


def test_signup_duplicate_email(client):
    client.post(
        "/v1/auth/signup",
        json={
            "email": "dup_email@example.com",
            "password": "password12",
            "nickname": "user1",
        },
    )
    res = client.post(
        "/v1/auth/signup",
        json={
            "email": "dup_email@example.com",
            "password": "password12",
            "nickname": "user2",
        },
    )
    assert res.status_code == 409
    assert res.json()["code"] == "EMAIL_ALREADY_EXISTS"


def test_signup_duplicate_nickname(client):
    client.post(
        "/v1/auth/signup",
        json={
            "email": "user_a@example.com",
            "password": "password12",
            "nickname": "samenick",
        },
    )
    res = client.post(
        "/v1/auth/signup",
        json={
            "email": "user_b@example.com",
            "password": "password12",
            "nickname": "samenick",
        },
    )
    assert res.status_code == 409
    assert res.json()["code"] == "NICKNAME_ALREADY_EXISTS"


def test_login_success(client):
    client.post(
        "/v1/auth/signup",
        json={
            "email": "login_ok@example.com",
            "password": "password12",
            "nickname": "loginuser",
        },
    )
    res = client.post(
        "/v1/auth/login",
        json={"email": "login_ok@example.com", "password": "password12"},
    )
    assert res.status_code == 200
    assert "set-cookie" in res.headers or res.cookies.get("session_id")
    data = res.json()
    assert data["code"] == "LOGIN_SUCCESS"
    assert "userId" in data.get("data", {})


def test_login_wrong_password(client):
    client.post(
        "/v1/auth/signup",
        json={
            "email": "wrong_pw@example.com",
            "password": "password12",
            "nickname": "wrongpw",
        },
    )
    res = client.post(
        "/v1/auth/login",
        json={"email": "wrong_pw@example.com", "password": "wrong"},
    )
    assert res.status_code == 401
    assert res.json()["code"] == "INVALID_CREDENTIALS"


def test_login_email_not_found(client):
    res = client.post(
        "/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "password12"},
    )
    assert res.status_code == 401
    assert res.json()["code"] == "INVALID_CREDENTIALS"


def test_me_unauthorized(client):
    res = client.get("/v1/users/me")
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHORIZED"


def test_me_success(client):
    client.post(
        "/v1/auth/signup",
        json={
            "email": "me_ok@example.com",
            "password": "password12",
            "nickname": "meuser",
        },
    )
    login = client.post(
        "/v1/auth/login", json={"email": "me_ok@example.com", "password": "password12"}
    )
    assert login.status_code == 200
    token = login.json().get("data", {}).get("accessToken") or login.json().get("data", {}).get(
        "access_token"
    )
    assert token
    res = client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["code"] == "USER_RETRIEVED"
    data = res.json().get("data", {})
    assert "id" in data or "userId" in data
    assert "nickname" in data


def test_logout_success(client, auth_cookies):
    res = client.post("/v1/auth/logout", cookies=auth_cookies)
    assert res.status_code == 200
    assert res.json()["code"] == "LOGOUT_SUCCESS"


def test_logout_then_me_unauthorized(client, auth_cookies):
    client.post("/v1/auth/logout", cookies=auth_cookies)
    res = client.get("/v1/users/me", cookies=auth_cookies)
    assert res.status_code == 401
