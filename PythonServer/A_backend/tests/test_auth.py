from shared.testing import make_unique_name

PASSWORD = "password123"


def _register(client, username):
    return client.post("/auth/register", json={"username": username, "password": PASSWORD})


def test_register_success(client):
    name = make_unique_name("alice")
    resp = _register(client, name)
    assert resp.status_code == 201
    assert resp.json()["username"] == name


def test_register_duplicate_rejected(client):
    name = make_unique_name("alice")
    _register(client, name)
    resp = _register(client, name)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_USER"


def test_register_rejects_too_long_username(client):
    resp = _register(client, "a" * 101)
    assert resp.status_code == 422


def test_login_success_sets_cookie(client):
    name = make_unique_name("bob")
    _register(client, name)
    resp = client.post("/auth/login", json={"username": name, "password": PASSWORD})
    assert resp.status_code == 200
    assert "session_id" in resp.cookies


def test_login_wrong_password_fails(client):
    name = make_unique_name("carol")
    _register(client, name)
    resp = client.post("/auth/login", json={"username": name, "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_without_login_returns_null(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() is None


def test_me_after_login_returns_user(client):
    name = make_unique_name("dave")
    _register(client, name)
    client.post("/auth/login", json={"username": name, "password": PASSWORD})
    resp = client.get("/auth/me")
    assert resp.json()["username"] == name


def test_logout_clears_session(client):
    name = make_unique_name("eve")
    _register(client, name)
    client.post("/auth/login", json={"username": name, "password": PASSWORD})
    client.post("/auth/logout")
    resp = client.get("/auth/me")
    assert resp.json() is None


def test_password_never_stored_in_plaintext(client):
    from A_backend import db

    name = make_unique_name("frank")
    _register(client, name)
    row = db.get_user_by_username(name)
    assert row["password_hash"] != PASSWORD
    assert PASSWORD not in row["password_hash"]
