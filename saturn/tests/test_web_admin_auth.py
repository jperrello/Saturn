import pytest


ADMIN_TOKEN = "brutus-admin-fixture-token"
WRONG = "brutus-wrong-fixture-token"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SATURN_ADMIN_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("SATURN_ADMIN_PASSWORD", "brutus-fixture-pw-min-12chars")
    monkeypatch.setenv("SATURN_DATA_DIR", str(tmp_path))
    import importlib
    import saturn.web as web
    importlib.reload(web)
    from fastapi.testclient import TestClient
    return TestClient(web.app)


PROTECTED_ROUTES = [
    ("GET",    "/api/services",                     None),
    ("POST",   "/api/services",                     {"name": "x", "deployment": "network", "api_type": "openai", "priority": 1}),
    ("DELETE", "/api/services/nonexistent",         None),
    ("POST",   "/api/services/nonexistent/start",   None),
    ("POST",   "/api/services/nonexistent/stop",    None),
    ("GET",    "/api/admin/config",                 None),
    ("POST",   "/api/admin/config",                 {}),
    ("POST",   "/api/system/tunnel/start",          {}),
    ("POST",   "/api/system/tunnel/stop",           {}),
    ("GET",    "/api/system/status",                None),
    ("GET",    "/api/mcp/servers",                  None),
    ("POST",   "/api/mcp/servers",                  {"name": "x", "command": "echo"}),
    ("DELETE", "/api/mcp/servers/nonexistent",      None),
]


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_route_401_without_auth(client, method, path, body):
    r = client.request(method, path, json=body)
    assert r.status_code == 401, (
        f"{method} {path} must return 401 without auth, got {r.status_code}"
    )


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_route_401_with_wrong_bearer(client, method, path, body):
    r = client.request(method, path, json=body, headers={"Authorization": f"Bearer {WRONG}"})
    assert r.status_code == 401


def test_admin_config_auth_matrix(client):
    """Single route, all three credential states. Currently red on the no-auth line."""
    no_auth   = client.get("/api/admin/config")
    wrong     = client.get("/api/admin/config", headers={"Authorization": f"Bearer {WRONG}"})
    correct   = client.get("/api/admin/config", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert no_auth.status_code == 401, "GET /api/admin/config without auth must 401 (currently leaks config)"
    assert wrong.status_code   == 401, "wrong bearer must 401"
    assert correct.status_code == 200, f"correct bearer must reach handler, got {correct.status_code}"


def test_forged_session_cookie_does_not_bypass(client):
    """sessionStorage was UI-only theatre. forged cookies must not pass server-side auth."""
    r = client.get(
        "/api/admin/config",
        cookies={"admin_session": "forged", "saturn_admin": "true", "isAdmin": "1"},
    )
    assert r.status_code == 401


def test_forged_header_does_not_bypass(client):
    r = client.get("/api/admin/config", headers={"X-Admin": "true", "X-Saturn-Admin": "1"})
    assert r.status_code == 401


PUBLIC_ROUTES = [
    ("POST", "/api/admin/auth", {"password": "wrong"}),  # public — issues the token; bad pw → 401 from password check, not auth-dep
    ("GET",  "/api/discover",   None),
    ("GET",  "/v1/health",      None),                   # /v1/* on web side has its own runner-token gate (qj5.16.1 territory); but /v1/health is in default public_routes per A.5
]


def test_public_admin_auth_accepts_request_shape(client):
    """/api/admin/auth must be reachable without prior auth (it issues the credential)."""
    r = client.post("/api/admin/auth", json={"password": "definitely-wrong"})
    assert r.status_code == 401, "wrong password is 401, but the route MUST accept the request — not 403/404/method-not-allowed"
    body = r.text.lower()
    assert "invalid password" in body or "password" in body, (
        "401 must come from password check (issuing route), not from a blanket auth dependency"
    )


def test_public_admin_auth_succeeds_with_correct_password(client):
    r = client.post("/api/admin/auth", json={"password": "brutus-fixture-pw-min-12chars"})
    assert r.status_code == 200


def test_discover_public(client):
    r = client.get("/api/discover")
    assert r.status_code != 401
