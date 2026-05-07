import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


TOKEN = "test-omlx-token-7im"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _wait_http(port, path="/v1/models", timeout=15.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}{path}", headers=AUTH, timeout=1.0)
            if r.status_code < 500:
                return r
        except Exception as e:
            last = e
        time.sleep(0.2)
    raise RuntimeError(f"server on :{port} never came up: {last}")


class _UpstreamHandler(BaseHTTPRequestHandler):
    def log_message(self, *a, **k): pass

    def _write(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/models":
            return self._write(200, {
                "object": "list",
                "data": [{"id": "omlx-test-model", "object": "model"}],
            })
        self._write(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(n)
        if self.path == "/v1/chat/completions":
            return self._write(200, {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "OMLX-FIXTURE-OK"},
                    "finish_reason": "stop",
                }],
            })
        if self.path == "/v1/embeddings":
            return self._write(200, {
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
            })
        if self.path == "/v1/messages":
            return self._write(200, {
                "id": "msg_test",
                "type": "message",
                "content": [{"type": "text", "text": "OMLX-FIXTURE-MSG"}],
            })
        if self.path == "/v1/rerank":
            return self._write(200, {"results": [{"index": 0, "relevance_score": 0.9}]})
        self._write(404, {"error": "not found"})


@pytest.fixture
def upstream():
    port = _free_port()
    srv = HTTPServer(("127.0.0.1", port), _UpstreamHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def saturn_omlx(upstream):
    sdir = Path(tempfile.mkdtemp(prefix="saturn-omlx-"))
    (sdir / "omlx.toml").write_text(f"""
name = "omlx"
deployment = "local"
api_type = "openai"
priority = 50

[upstream]
base_url = "http://127.0.0.1:{upstream}/v1"

[server]
port = 0

[beacon]
enabled = false
""".lstrip())
    saturn_port = _free_port()
    env = dict(os.environ)
    env["SATURN_SERVICES_DIR"] = str(sdir)
    env["SATURN_RUNNER_TOKEN"] = TOKEN
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(
        [sys.executable, "-m", "saturn", "run", "omlx",
         "--host", "127.0.0.1", "--port", str(saturn_port)],
        cwd=str(REPO), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        _wait_http(saturn_port, "/v1/models", timeout=20.0)
    except Exception:
        try:
            out, err = p.communicate(timeout=2.0)
        except Exception:
            p.kill()
            out, err = p.communicate()
        raise AssertionError(
            f"saturn run omlx failed to start (behavior missing).\n"
            f"stdout={out!r}\nstderr={err!r}"
        )
    yield saturn_port
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=3.0)
        except Exception:
            p.kill()
            p.wait(timeout=3.0)


# Invariant 1 — built-in service profile exists with the right shape
def test_omlx_profile_shipped():
    builtin = REPO / "saturn" / "services" / "omlx.toml"
    assert builtin.exists(), f"missing {builtin}"
    text = builtin.read_text()
    assert 'name = "omlx"' in text
    assert 'api_type = "openai"' in text
    assert "localhost:8000/v1" in text or "127.0.0.1:8000/v1" in text, \
        "omlx.toml must default to upstream localhost:8000/v1 (jundot/omlx default)"


# Invariant 2 — provider module is importable
def test_omlx_provider_module_importable():
    import importlib
    mod = importlib.import_module("saturn.providers.omlx")
    assert mod is not None


# Invariant 3 — saturn run omlx proxies /v1/models from upstream
def test_omlx_models_proxied(saturn_omlx):
    r = httpx.get(f"http://127.0.0.1:{saturn_omlx}/v1/models", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [m.get("id") for m in body.get("data", [])]
    assert "omlx-test-model" in ids, f"models not proxied: {body}"


# Invariant 4 — saturn run omlx proxies /v1/chat/completions
def test_omlx_chat_proxied(saturn_omlx):
    r = httpx.post(
        f"http://127.0.0.1:{saturn_omlx}/v1/chat/completions",
        json={"model": "omlx-test-model", "messages": [{"role": "user", "content": "hi"}]},
        headers=AUTH, timeout=5.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    content = body["choices"][0]["message"]["content"]
    assert content == "OMLX-FIXTURE-OK", f"chat not proxied: {body}"


# Invariant 5 — saturn run omlx proxies /v1/embeddings
def test_omlx_embeddings_proxied(saturn_omlx):
    r = httpx.post(
        f"http://127.0.0.1:{saturn_omlx}/v1/embeddings",
        json={"model": "omlx-test-model", "input": "hi"},
        headers=AUTH, timeout=5.0,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"][0]["embedding"] == [0.1, 0.2]


# Invariant 5b — /v1/messages (Anthropic surface) proxied
def test_omlx_messages_proxied(saturn_omlx):
    r = httpx.post(
        f"http://127.0.0.1:{saturn_omlx}/v1/messages",
        json={"model": "omlx-test-model", "messages": [{"role": "user", "content": "hi"}]},
        headers=AUTH, timeout=5.0,
    )
    assert r.status_code == 200, f"/v1/messages -> {r.status_code} {r.text!r}"
    assert "OMLX-FIXTURE-MSG" in r.text


# Invariant 5c — /v1/rerank proxied
def test_omlx_rerank_proxied(saturn_omlx):
    r = httpx.post(
        f"http://127.0.0.1:{saturn_omlx}/v1/rerank",
        json={"model": "omlx-test-model", "query": "q", "documents": ["a"]},
        headers=AUTH, timeout=5.0,
    )
    assert r.status_code == 200, f"/v1/rerank -> {r.status_code} {r.text!r}"


# Invariant 6 — saturn advertises omlx as openai api_type on _saturn._tcp.local.
def test_omlx_advertises_openai(saturn_omlx):
    from saturn.discovery import discover
    services = discover(timeout=5.0)
    mine = [s for s in services if s.port == saturn_omlx]
    assert mine, f"saturn omlx not in discovery: {[(s.name, s.port) for s in services]}"
    assert mine[0].api_type == "openai", f"wrong api_type: {mine[0].api_type}"


# Invariant 7 — config loadable through saturn.config.load_service_config
def test_omlx_config_loadable():
    from saturn.config import load_service_config, BUILTIN_SERVICES_DIR
    assert (BUILTIN_SERVICES_DIR / "omlx.toml").exists()
    cfg = load_service_config("omlx")
    assert cfg is not None
    assert cfg.api_type == "openai"
    assert cfg.upstream.base_url.endswith("/v1")
    assert ":8000" in cfg.upstream.base_url
