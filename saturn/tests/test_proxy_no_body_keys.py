"""Saturn-qj5.16.6 + qj5.16.7 — combined contract.

F-5: /api/proxy/chat ManualChatRequest must reject body-supplied api_key (extra="forbid").
F-6: /api/proxy/models must reject query-string api_key.
Both: pass through inbound Authorization: Bearer header verbatim.
Both: sanitise upstream error reflection.
"""

import http.server
import socket
import threading

import pytest


@pytest.fixture
def upstream():
    received = []
    state = {"status": 200, "body": b'{"data": [{"id": "model-x"}]}'}

    class Handler(http.server.BaseHTTPRequestHandler):
        def _serve(self):
            received.append(dict(self.headers.items()))
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(state["body"])))
            self.end_headers()
            self.wfile.write(state["body"])

        do_GET = _serve
        do_POST = _serve

        def log_message(self, *a, **k):
            pass

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield {
            "url": f"http://127.0.0.1:{port}",
            "received": received,
            "state": state,
        }
    finally:
        server.shutdown()


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SATURN_ADMIN_TOKEN", "brutus-fixture-token")
    monkeypatch.setenv("SATURN_ADMIN_PASSWORD", "brutus-fixture-pw-min-12chars")
    monkeypatch.setenv("SATURN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SATURN_RATE_RPM", "100000")
    monkeypatch.setenv("SATURN_RATE_TPM", "100000000")
    monkeypatch.setenv("SATURN_RATE_CONCURRENT", "64")
    import importlib
    import saturn.web as web
    importlib.reload(web)
    from fastapi.testclient import TestClient
    return TestClient(web.app)


# --- F-5: /api/proxy/chat ---

def test_proxy_chat_rejects_body_api_key(client, upstream):
    """Body-supplied api_key field must be rejected (extra='forbid' on ManualChatRequest)."""
    r = client.post(
        "/api/proxy/chat",
        json={
            "base_url": upstream["url"],
            "model": "model-x",
            "messages": [{"role": "user", "content": "hi"}],
            "api_key": "sk-real-secret-must-not-be-accepted",
        },
    )
    assert r.status_code == 422, (
        f"body-supplied api_key must be rejected by Pydantic; got {r.status_code}. "
        f"ManualChatRequest needs the field deleted AND model_config = ConfigDict(extra='forbid')."
    )


def test_proxy_chat_passthrough_authorization_header(client, upstream):
    """Inbound Authorization: Bearer X must reach the upstream verbatim."""
    bearer = "passthrough-token-9f3a"
    client.post(
        "/api/proxy/chat",
        json={
            "base_url": upstream["url"],
            "model": "model-x",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert upstream["received"], "upstream was never hit — request never proxied"
    auths = [h.get("Authorization") or h.get("authorization") for h in upstream["received"]]
    assert f"Bearer {bearer}" in auths, (
        f"upstream did not receive passthrough bearer; got auth headers: {auths!r}"
    )


def test_proxy_chat_does_not_echo_upstream_error_body(client, upstream):
    """Upstream non-200 body must not be reflected verbatim in the SSE stream (§11.5)."""
    upstream["state"]["status"] = 401
    upstream["state"]["body"] = b'{"error": "leaked upstream secret echo Bearer ******abc"}'
    r = client.post(
        "/api/proxy/chat",
        json={
            "base_url": upstream["url"],
            "model": "model-x",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    text = r.text
    assert "leaked upstream secret echo" not in text, (
        f"upstream error body reflected verbatim into SSE: {text!r}"
    )
    assert "******abc" not in text


# --- F-6: /api/proxy/models ---

def test_proxy_models_rejects_query_api_key(client, upstream):
    """Query-string api_key must be rejected (signature must drop the parameter)."""
    r = client.get(
        f"/api/proxy/models?base_url={upstream['url']}&api_key=sk-leaks-via-url"
    )
    assert r.status_code == 422, (
        f"query-string api_key must be rejected; got {r.status_code}. "
        f"Drop the api_key Query parameter from proxy_models signature."
    )


def test_proxy_models_passthrough_authorization_header(client, upstream):
    """Inbound Authorization: Bearer X must reach the upstream verbatim."""
    bearer = "models-passthrough-token-7c1d"
    client.get(
        f"/api/proxy/models?base_url={upstream['url']}",
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert upstream["received"], "upstream was never hit"
    auths = [h.get("Authorization") or h.get("authorization") for h in upstream["received"]]
    assert f"Bearer {bearer}" in auths, (
        f"upstream did not receive passthrough bearer; got: {auths!r}"
    )


def test_proxy_models_502_does_not_leak_upstream_details(client, upstream):
    """Upstream failure must surface as 502 with a constant string — no upstream URL or exception text."""
    upstream["state"]["status"] = 401
    upstream["state"]["body"] = b'{"error": "secret-fragment-xyz"}'
    r = client.get(f"/api/proxy/models?base_url={upstream['url']}")
    assert r.status_code == 502
    body = r.text
    assert upstream["url"] not in body, f"upstream URL leaked into 502 body: {body!r}"
    assert "secret-fragment-xyz" not in body, f"upstream exception text leaked: {body!r}"
