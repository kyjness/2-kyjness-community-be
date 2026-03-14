MINIMAL_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def test_upload_requires_auth(client):
    res = client.post(
        "/v1/media/images",
        files={"image": ("x.jpg", MINIMAL_JPEG, "image/jpeg")},
        params={"purpose": "post"},
    )
    assert res.status_code == 401


def test_upload_success(client, auth_cookies):
    res = client.post(
        "/v1/media/images",
        files={"image": ("test.jpg", MINIMAL_JPEG, "image/jpeg")},
        params={"purpose": "post"},
        cookies=auth_cookies,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "IMAGE_UPLOADED"
    assert "imageId" in data["data"]
    assert "url" in data["data"]
    return data["data"]["imageId"]


def test_upload_profile_type(client, auth_cookies):
    res = client.post(
        "/v1/media/images",
        files={"image": ("p.jpg", MINIMAL_JPEG, "image/jpeg")},
        params={"purpose": "profile"},
        cookies=auth_cookies,
    )
    assert res.status_code == 201
    assert res.json()["code"] == "IMAGE_UPLOADED"


def test_delete_requires_auth(client):
    res = client.delete("/v1/media/images/1")
    assert res.status_code == 401


def test_delete_not_found(client, auth_cookies):
    res = client.delete("/v1/media/images/99999", cookies=auth_cookies)
    assert res.status_code == 404
    assert res.json()["code"] == "IMAGE_NOT_FOUND"


def test_delete_success(client, auth_cookies):
    upload = client.post(
        "/v1/media/images",
        files={"image": ("del.jpg", MINIMAL_JPEG, "image/jpeg")},
        params={"purpose": "post"},
        cookies=auth_cookies,
    )
    assert upload.status_code == 201
    image_id = upload.json()["data"]["imageId"]
    res = client.delete(f"/v1/media/images/{image_id}", cookies=auth_cookies)
    assert res.status_code == 204
    delete_again = client.delete(f"/v1/media/images/{image_id}", cookies=auth_cookies)
    assert delete_again.status_code == 404
