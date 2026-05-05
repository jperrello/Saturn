import pytest


ADMIN_TOKEN = "brutus-usage-fixture-token"


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


def _admin(headers=None):
    h = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    if headers:
        h.update(headers)
    return h


def test_usage_401_without_auth(client):
    assert client.get("/api/usage").status_code == 401
    assert client.get("/api/usage?user_id=10.0.0.42").status_code == 401


def test_usage_history_401_without_auth(client):
    assert client.get("/api/usage/history").status_code == 401
    assert client.get("/api/usage/history?user_id=10.0.0.42&days=7").status_code == 401


def test_usage_401_with_wrong_bearer(client):
    r = client.get("/api/usage?user_id=10.0.0.42", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_usage_admin_can_read_any_row(client):
    """Admin-supplied user_id reads that row intentionally (per §9.6)."""
    target = "10.0.0.42"
    r = client.post("/api/usage/report", json={"tokens_in": 11, "tokens_out": 22},
                    headers={"X-Forwarded-For": target})  # caller's _client_ip — post-§8 may or may not honor XFF
    assert r.status_code == 200
    seed_ip = client.get("/api/usage", headers=_admin()).json().get("user_id")

    r = client.get(f"/api/usage?user_id={seed_ip}", headers=_admin())
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == seed_ip
    assert body["tokens_in"] == 11
    assert body["tokens_out"] == 22


def test_usage_history_auth_matrix(client):
    """no-auth → 401, admin → 200 list. Currently red on the no-auth line."""
    no_auth = client.get("/api/usage/history?days=7")
    admin = client.get("/api/usage/history?days=7", headers=_admin())
    assert no_auth.status_code == 401
    assert admin.status_code == 200
    assert isinstance(admin.json(), list)


def test_usage_report_forged_user_id_does_not_attribute(client):
    """§9.6: 'a peer cannot inject a row attributed to another IP via any header or body field.'
    Combined with the auth-gate assertion so this fails NOW (the admin-lookup step requires the auth fix)."""
    forged = "10.0.0.99"
    rep = client.post(
        "/api/usage/report",
        json={"tokens_in": 7, "tokens_out": 8, "user_id": forged},
    )
    assert rep.status_code in (200, 422), f"either accept-and-ignore or reject; got {rep.status_code}"

    # This GET must require admin auth — failing now because route is unauth.
    no_auth = client.get(f"/api/usage?user_id={forged}")
    assert no_auth.status_code == 401, "GET /api/usage must require admin auth"

    check = client.get(f"/api/usage?user_id={forged}", headers=_admin()).json()
    assert check["tokens_in"] == 0 and check["tokens_out"] == 0, (
        f"forged body user_id={forged!r} attributed tokens it should not have: {check}"
    )
