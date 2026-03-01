def test_availability_no_param(client):
    res = client.get("/v1/users/availability")
    assert res.status_code == 400
    assert res.json()["code"] == "INVALID_REQUEST"


def test_availability_email_available(client):
    res = client.get("/v1/users/availability?email=newemail@example.com")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "OK"
    assert data["data"]["emailAvailable"] is True


def test_availability_email_taken(client):
    client.post(
        "/v1/auth/signup",
        json={"email": "taken_email@example.com", "password": "password12", "nickname": "takenemail"},
    )
    res = client.get("/v1/users/availability?email=taken_email@example.com")
    assert res.status_code == 200
    assert res.json()["data"]["emailAvailable"] is False


def test_availability_nickname_available(client):
    res = client.get("/v1/users/availability?nickname=uniquenick999")
    assert res.status_code == 200
    assert res.json()["data"]["nicknameAvailable"] is True


def test_availability_nickname_taken(client):
    client.post(
        "/v1/auth/signup",
        json={"email": "nick_taken@example.com", "password": "password12", "nickname": "taken_nick"},
    )
    res = client.get("/v1/users/availability?nickname=taken_nick")
    assert res.status_code == 200
    assert res.json()["data"]["nicknameAvailable"] is False


def test_me_unauthorized(client):
    res = client.get("/v1/users/me")
    assert res.status_code == 401


def test_me_success(client, auth_cookies):
    res = client.get("/v1/users/me", cookies=auth_cookies)
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "USER_RETRIEVED"
    assert "userId" in data["data"]
    assert data["data"]["email"] == "auth_user@example.com"
    assert data["data"]["nickname"] == "auth_user"


def test_update_me_unauthorized(client):
    res = client.patch(
        "/v1/users/me",
        json={"nickname": "newnick"},
    )
    assert res.status_code == 401


def test_update_me_success(client, auth_cookies):
    res = client.patch(
        "/v1/users/me",
        json={"nickname": "updated_nick"},
        cookies=auth_cookies,
    )
    assert res.status_code == 200
    assert res.json()["code"] == "USER_UPDATED"
    me = client.get("/v1/users/me", cookies=auth_cookies).json()
    assert me["data"]["nickname"] == "updated_nick"


def test_update_me_duplicate_nickname(client, auth_cookies):
    client.post(
        "/v1/auth/signup",
        json={"email": "other@example.com", "password": "password12", "nickname": "taken_nick"},
    )
    res = client.patch(
        "/v1/users/me",
        json={"nickname": "taken_nick"},
        cookies=auth_cookies,
    )
    assert res.status_code == 409
    assert res.json()["code"] == "NICKNAME_ALREADY_EXISTS"


def test_update_password_unauthorized(client):
    res = client.patch(
        "/v1/users/me/password",
        json={"currentPassword": "password12", "newPassword": "newpass12"},
    )
    assert res.status_code == 401


def test_update_password_wrong_current(client, auth_cookies):
    res = client.patch(
        "/v1/users/me/password",
        json={"currentPassword": "wrong", "newPassword": "newpass12"},
        cookies=auth_cookies,
    )
    assert res.status_code == 401


def test_update_password_success(client):
    from test.conftest import _login
    cookies = _login(client, "pw_user@example.com", "oldpass12")
    res = client.patch(
        "/v1/users/me/password",
        json={"currentPassword": "oldpass12", "newPassword": "newpass12"},
        cookies=cookies,
    )
    assert res.status_code == 200
    assert res.json()["code"] == "PASSWORD_UPDATED"
    client.post("/v1/auth/logout", cookies=cookies)
    login_old = client.post("/v1/auth/login", json={"email": "pw_user@example.com", "password": "oldpass12"})
    assert login_old.status_code == 401
    login_new = client.post("/v1/auth/login", json={"email": "pw_user@example.com", "password": "newpass12"})
    assert login_new.status_code == 200


def test_delete_me_unauthorized(client):
    res = client.delete("/v1/users/me")
    assert res.status_code == 401


def test_delete_me_success(client):
    from test.conftest import _login
    cookies = _login(client, "delete_user@example.com", "password12")
    res = client.delete("/v1/users/me", cookies=cookies)
    assert res.status_code == 204
    me_res = client.get("/v1/users/me", cookies=cookies)
    assert me_res.status_code == 401
