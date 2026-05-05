import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SATURN_ADMIN_TOKEN", "x" * 32)
    monkeypatch.setenv("SATURN_ADMIN_PASSWORD", "session-fixture-pw")
    monkeypatch.setenv("SATURN_DATA_DIR", str(tmp_path))
    import importlib
    import saturn.web as web
    importlib.reload(web)
    from fastapi.testclient import TestClient
    return TestClient(web.app, follow_redirects=False)


def test_root_unauth_redirects_to_login(client):
    r = client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_page_public(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "Saturn" in r.text


def test_status_first_run_must_change(client):
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    assert r.json() == {"authenticated": False, "must_change": True}


def test_login_default_password_works_first_run(client):
    r = client.post("/api/auth/login", json={"password": "Saturn"})
    assert r.status_code == 200
    assert r.json()["must_change"] is True
    assert "saturn_session" in r.cookies


def test_wrong_password_rejected(client):
    r = client.post("/api/auth/login", json={"password": "nope"})
    assert r.status_code == 401


def test_session_cookie_unlocks_root(client):
    r = client.post("/api/auth/login", json={"password": "Saturn"})
    assert r.status_code == 200
    r2 = client.get("/")
    assert r2.status_code == 200


def test_change_password_flow(client):
    client.post("/api/auth/login", json={"password": "Saturn"})
    r = client.post("/api/auth/password", json={"old": "Saturn", "new": "newpass1"})
    assert r.status_code == 200
    client.cookies.clear()
    r2 = client.post("/api/auth/login", json={"password": "Saturn"})
    assert r2.status_code == 401
    r3 = client.post("/api/auth/login", json={"password": "newpass1"})
    assert r3.status_code == 200
    assert r3.json()["must_change"] is False


def test_logout_clears_session(client):
    client.post("/api/auth/login", json={"password": "Saturn"})
    r = client.post("/api/auth/logout")
    assert r.status_code == 200
    client.cookies.clear()
    r2 = client.get("/", follow_redirects=False)
    assert r2.status_code == 303


def test_short_new_password_rejected(client):
    client.post("/api/auth/login", json={"password": "Saturn"})
    r = client.post("/api/auth/password", json={"old": "Saturn", "new": "abc"})
    assert r.status_code == 400
