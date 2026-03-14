def test_create_requires_auth(client):
    res = client.post(
        "/v1/posts/1/comments",
        json={"content": "hello"},
    )
    assert res.status_code == 401


def test_create_post_not_found(client, auth_cookies):
    res = client.post(
        "/v1/posts/99999/comments",
        json={"content": "hello"},
        cookies=auth_cookies,
    )
    assert res.status_code == 404
    assert res.json()["code"] == "POST_NOT_FOUND"


def test_create_success(client, auth_cookies):
    create_post = client.post(
        "/v1/posts",
        json={"title": "Comment post", "content": "body"},
        cookies=auth_cookies,
    )
    assert create_post.status_code == 201
    post_id = create_post.json()["data"]["postId"]
    res = client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "first comment"},
        cookies=auth_cookies,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "COMMENT_UPLOADED"
    assert "commentId" in data["data"]
    return post_id, data["data"]["commentId"]


def test_list_post_not_found(client):
    res = client.get("/v1/posts/99999/comments?page=1&size=10")
    assert res.status_code == 404
    assert res.json()["code"] == "POST_NOT_FOUND"


def test_list_empty(client, auth_cookies):
    create_post = client.post(
        "/v1/posts",
        json={"title": "No comments", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create_post.json()["data"]["postId"]
    res = client.get(f"/v1/posts/{post_id}/comments?page=1&size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "COMMENTS_RETRIEVED"
    assert data["data"]["list"] == []
    assert data["data"]["totalCount"] == 0
    assert data["data"]["totalPages"] == 1
    assert data["data"]["currentPage"] == 1


def test_list_with_comments(client, auth_cookies):
    create_post = client.post(
        "/v1/posts",
        json={"title": "With comments", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create_post.json()["data"]["postId"]
    client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "one"},
        cookies=auth_cookies,
    )
    client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "two"},
        cookies=auth_cookies,
    )
    res = client.get(f"/v1/posts/{post_id}/comments?page=1&size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "COMMENTS_RETRIEVED"
    assert data["data"]["totalCount"] == 2
    assert len(data["data"]["list"]) == 2
    contents = [c["content"] for c in data["data"]["list"]]
    assert "one" in contents and "two" in contents


def test_update_requires_auth(client):
    res = client.patch(
        "/v1/posts/1/comments/1",
        json={"content": "updated"},
    )
    assert res.status_code == 401


def test_update_comment_not_found(client, auth_cookies):
    create_post = client.post(
        "/v1/posts",
        json={"title": "P", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create_post.json()["data"]["postId"]
    res = client.patch(
        f"/v1/posts/{post_id}/comments/99999",
        json={"content": "updated"},
        cookies=auth_cookies,
    )
    assert res.status_code == 404
    assert res.json()["code"] == "COMMENT_NOT_FOUND"


def test_update_success(client, auth_cookies):
    create_post = client.post(
        "/v1/posts",
        json={"title": "Edit comment", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create_post.json()["data"]["postId"]
    create_c = client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "original"},
        cookies=auth_cookies,
    )
    comment_id = create_c.json()["data"]["commentId"]
    res = client.patch(
        f"/v1/posts/{post_id}/comments/{comment_id}",
        json={"content": "edited"},
        cookies=auth_cookies,
    )
    assert res.status_code == 200
    assert res.json()["code"] == "COMMENT_UPDATED"
    list_res = client.get(f"/v1/posts/{post_id}/comments?page=1&size=10")
    found = next(c for c in list_res.json()["data"]["list"] if c["commentId"] == comment_id)
    assert found["content"] == "edited"


def test_delete_requires_auth(client):
    res = client.delete("/v1/posts/1/comments/1")
    assert res.status_code == 401


def test_delete_comment_not_found(client, auth_cookies):
    create_post = client.post(
        "/v1/posts",
        json={"title": "P", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create_post.json()["data"]["postId"]
    res = client.delete(
        f"/v1/posts/{post_id}/comments/99999",
        cookies=auth_cookies,
    )
    assert res.status_code == 404


def test_delete_success(client, auth_cookies):
    create_post = client.post(
        "/v1/posts",
        json={"title": "Delete comment", "content": "x"},
        cookies=auth_cookies,
    )
    post_id = create_post.json()["data"]["postId"]
    create_c = client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "to delete"},
        cookies=auth_cookies,
    )
    comment_id = create_c.json()["data"]["commentId"]
    res = client.delete(
        f"/v1/posts/{post_id}/comments/{comment_id}",
        cookies=auth_cookies,
    )
    assert res.status_code == 204
    list_res = client.get(f"/v1/posts/{post_id}/comments?page=1&size=10")
    ids = [c["commentId"] for c in list_res.json()["data"]["list"]]
    assert comment_id not in ids
