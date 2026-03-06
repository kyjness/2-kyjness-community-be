def test_list_empty(client):
    res = client.get("/v1/posts?page=1&size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "POSTS_RETRIEVED"
    assert "list" in data["data"] and "hasMore" in data["data"]
    assert data["data"]["list"] == []
    assert data["data"]["hasMore"] is False


def test_detail_not_found(client):
    res = client.get("/v1/posts/99999")
    assert res.status_code == 404
    assert res.json()["code"] == "POST_NOT_FOUND"


def test_create_requires_auth(client):
    res = client.post("/v1/posts", json={"title": "t", "content": "c"})
    assert res.status_code == 401


def test_create_success(client, auth_cookies):
    res = client.post(
        "/v1/posts",
        json={"title": "Hello", "content": "World"},
        cookies=auth_cookies,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "POST_UPLOADED"
    assert "postId" in data["data"]
    return data["data"]["postId"]


def test_list_after_create(client, auth_cookies):
    client.post(
        "/v1/posts",
        json={"title": "List me", "content": "Body"},
        cookies=auth_cookies,
    )
    res = client.get("/v1/posts?page=1&size=10")
    assert res.status_code == 200
    assert res.json()["code"] == "POSTS_RETRIEVED"
    lst = res.json()["data"]["list"]
    assert len(lst) >= 1
    first = lst[0]
    assert first["title"] == "List me"
    assert first["contentPreview"] == "Body"


def test_detail_success(client, auth_cookies):
    create = client.post(
        "/v1/posts",
        json={"title": "Detail post", "content": "Full content here"},
        cookies=auth_cookies,
    )
    assert create.status_code == 201
    post_id = create.json()["data"]["postId"]
    res = client.get(f"/v1/posts/{post_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "POST_RETRIEVED"
    assert data["data"]["title"] == "Detail post"
    assert data["data"]["content"] == "Full content here"


def test_view_increments(client, auth_cookies):
    create = client.post(
        "/v1/posts",
        json={"title": "View post", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create.json()["data"]["postId"]
    res = client.post(f"/v1/posts/{post_id}/view")
    assert res.status_code == 204
    get_res = client.get(f"/v1/posts/{post_id}")
    assert get_res.json()["data"]["hits"] >= 1


def test_update_requires_auth(client):
    res = client.patch("/v1/posts/1", json={"title": "t", "content": "c"})
    assert res.status_code == 401


def test_update_not_found(client, auth_cookies):
    res = client.patch(
        "/v1/posts/99999",
        json={"title": "t", "content": "c"},
        cookies=auth_cookies,
    )
    assert res.status_code == 404


def test_update_success(client, auth_cookies):
    create = client.post(
        "/v1/posts",
        json={"title": "Original", "content": "Body"},
        cookies=auth_cookies,
    )
    post_id = create.json()["data"]["postId"]
    res = client.patch(
        f"/v1/posts/{post_id}",
        json={"title": "Updated", "content": "New body"},
        cookies=auth_cookies,
    )
    assert res.status_code == 200
    assert res.json()["code"] == "POST_UPDATED"
    get_res = client.get(f"/v1/posts/{post_id}")
    assert get_res.json()["data"]["title"] == "Updated"
    assert get_res.json()["data"]["content"] == "New body"


def test_delete_requires_auth(client):
    res = client.delete("/v1/posts/1")
    assert res.status_code == 401


def test_delete_not_found(client, auth_cookies):
    res = client.delete("/v1/posts/99999", cookies=auth_cookies)
    assert res.status_code == 404


def test_delete_success(client, auth_cookies):
    create = client.post(
        "/v1/posts",
        json={"title": "To delete", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create.json()["data"]["postId"]
    res = client.delete(f"/v1/posts/{post_id}", cookies=auth_cookies)
    assert res.status_code == 204
    get_res = client.get(f"/v1/posts/{post_id}")
    assert get_res.status_code == 404


def test_add_like_requires_auth(client):
    res = client.post("/v1/posts/1/likes")
    assert res.status_code == 401


def test_add_like_not_found(client, auth_cookies):
    res = client.post("/v1/posts/99999/likes", cookies=auth_cookies)
    assert res.status_code == 404


def test_add_like_success(client, auth_cookies):
    create = client.post(
        "/v1/posts",
        json={"title": "Like post", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create.json()["data"]["postId"]
    res = client.post(f"/v1/posts/{post_id}/likes", cookies=auth_cookies)
    assert res.status_code == 201
    assert res.json()["code"] == "LIKE_SUCCESS"
    assert "likeCount" in res.json()["data"]


def test_add_like_already_liked(client, auth_cookies):
    create = client.post(
        "/v1/posts",
        json={"title": "Double like", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create.json()["data"]["postId"]
    client.post(f"/v1/posts/{post_id}/likes", cookies=auth_cookies)
    res = client.post(f"/v1/posts/{post_id}/likes", cookies=auth_cookies)
    assert res.status_code == 200
    assert res.json()["code"] == "ALREADY_LIKED"


def test_delete_like_requires_auth(client):
    res = client.delete("/v1/posts/1/likes")
    assert res.status_code == 401


def test_delete_like_not_found(client, auth_cookies):
    res = client.delete("/v1/posts/99999/likes", cookies=auth_cookies)
    assert res.status_code == 404


def test_delete_like_success(client, auth_cookies):
    create = client.post(
        "/v1/posts",
        json={"title": "Unlike post", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create.json()["data"]["postId"]
    client.post(f"/v1/posts/{post_id}/likes", cookies=auth_cookies)
    res = client.delete(f"/v1/posts/{post_id}/likes", cookies=auth_cookies)
    assert res.status_code == 204


def test_delete_like_when_not_liked(client, auth_cookies):
    create = client.post(
        "/v1/posts",
        json={"title": "No like", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create.json()["data"]["postId"]
    res = client.delete(f"/v1/posts/{post_id}/likes", cookies=auth_cookies)
    assert res.status_code == 204
