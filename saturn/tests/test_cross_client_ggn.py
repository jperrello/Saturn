"""Saturn-ggn / cbt.cross-client — /v1/* contract tests across HTTP stacks.

Phase 3 API guarantee. Every /v1/* endpoint MUST return semantically
identical responses regardless of which HTTP client the caller uses. This
contract pins the invariant against three distinct stacks:

  1. Python urllib   (stdlib)
  2. Python httpx    (async-native, Saturn's own client)
  3. subprocess curl (libcurl-based reference)

Go (`net/http`) is deferred — no Go test harness in this repo. File
**Saturn-ggn.go** if a Go harness lands.

Endpoints exercised:

  - GET  /v1/health
  - GET  /v1/models
  - POST /v1/chat/completions  (non-streaming)
  - POST /v1/chat/completions  (streaming SSE)

The oracle compares a *canonical* extracted form per endpoint, not raw
bytes — fields like `created` (unix timestamp) and `id` (per-call uuid)
naturally vary even within one client across calls. The canonical forms
strip those.

NO MOCKS. Real ServiceRunner subprocess against real Ollama.
"""

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

from .conftest_b3 import _free, _ping


pytestmark = pytest.mark.timeout(180)


@pytest.fixture(scope="session")
def ollama_available():
    if not _ping("http://localhost:11434/api/tags"):
        pytest.skip("Ollama not running")
    return "qwen2.5:0.5b"


RUNNER_SRC = textwrap.dedent('''
    import os
    from saturn.config import ServiceConfig, UpstreamConfig
    from saturn.runner import ServiceRunner
    import uvicorn

    cfg = ServiceConfig(
        name="ggn-runner",
        deployment="local",
        api_type="ollama",
        upstream=UpstreamConfig(base_url="http://localhost:11434/v1"),
    )
    runner = ServiceRunner(cfg)
    app = runner.create_app()
    if __name__ == "__main__":
        uvicorn.run(app, host="127.0.0.1", port=int(os.environ["PORT"]),
                    log_level="warning")
''')


@pytest.fixture
def runner_subprocess(tmp_path, ollama_available):
    src = tmp_path / "runner_main.py"
    src.write_text(RUNNER_SRC)
    port = _free()
    token = "brutus-ggn-" + secrets.token_urlsafe(32)
    env = {**os.environ, "PORT": str(port), "SATURN_RUNNER_TOKEN": token}
    log = open(tmp_path / "runner.log", "wb")
    proc = subprocess.Popen([sys.executable, str(src)], env=env,
                            stdout=log, stderr=log)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    up = False
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{base}/v1/health",
                                         headers={"Authorization": f"Bearer {token}"})
            urllib.request.urlopen(req, timeout=1).read()
            up = True
            break
        except (urllib.error.URLError, ConnectionResetError, OSError):
            time.sleep(0.2)
    if not up:
        try: proc.terminate()
        except Exception: pass
        log.close()
        pytest.fail(f"runner did not come up; see {tmp_path / 'runner.log'}")
    try:
        yield {"base": base, "token": token}
    finally:
        try: proc.terminate()
        except Exception: pass
        try: proc.wait(timeout=3)
        except Exception:
            try: proc.kill()
            except Exception: pass


# --- per-client GET helpers -------------------------------------------------

def _get_urllib(base, token, path):
    req = urllib.request.Request(f"{base}{path}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


def _get_httpx(base, token, path):
    import httpx
    r = httpx.get(f"{base}{path}",
                  headers={"Authorization": f"Bearer {token}"},
                  timeout=15.0)
    return r.status_code, r.json()


def _get_curl(base, token, path):
    p = subprocess.run(
        ["curl", "-sS", "-w", "\n%{http_code}",
         "-H", f"Authorization: Bearer {token}",
         f"{base}{path}"],
        capture_output=True, timeout=15, check=True,
    )
    out = p.stdout.decode()
    body, _, code = out.rpartition("\n")
    return int(code.strip()), json.loads(body)


# --- per-client POST helpers ------------------------------------------------

def _post_urllib(base, token, path, body, stream=False):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{base}{path}", data=data,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=60)
    text = r.read().decode("utf-8", "replace")
    if stream:
        return r.status, text
    return r.status, json.loads(text)


def _post_httpx(base, token, path, body, stream=False):
    import httpx
    if stream:
        with httpx.stream(
            "POST", f"{base}{path}", json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        ) as r:
            chunks = []
            for line in r.iter_lines():
                chunks.append(line)
            return r.status_code, "\n".join(chunks)
    r = httpx.post(f"{base}{path}", json=body,
                   headers={"Authorization": f"Bearer {token}"},
                   timeout=60.0)
    return r.status_code, r.json()


def _post_curl(base, token, path, body, stream=False):
    args = ["curl", "-sS", "-N", "-w", "\n__STATUS__%{http_code}",
            "-H", f"Authorization: Bearer {token}",
            "-H", "Content-Type: application/json",
            "-X", "POST", "-d", json.dumps(body),
            f"{base}{path}"]
    p = subprocess.run(args, capture_output=True, timeout=60, check=True)
    out = p.stdout.decode("utf-8", "replace")
    body_text, _, status_marker = out.rpartition("__STATUS__")
    code = int(status_marker.strip())
    if stream:
        return code, body_text.rstrip("\n")
    return code, json.loads(body_text)


# --- canonicalisers ---------------------------------------------------------

def _canon_health(payload):
    return {k: payload[k] for k in ("status", "saturn", "deployment", "api_type") if k in payload}


def _canon_models(payload):
    data = payload.get("data") or []
    return sorted(m.get("id") for m in data if isinstance(m, dict))


def _canon_chat_nostream(payload):
    choices = payload.get("choices") or []
    msg = (choices[0] or {}).get("message") if choices else {}
    return {
        "model": payload.get("model"),
        "finish_reason": (choices[0] or {}).get("finish_reason") if choices else None,
        "role": (msg or {}).get("role"),
        "content_present": bool((msg or {}).get("content")),
    }


def _canon_chat_stream(text):
    content = []
    finish = None
    model = None
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if obj.get("model"):
            model = obj["model"]
        for c in obj.get("choices") or []:
            d = c.get("delta") or {}
            if isinstance(d.get("content"), str):
                content.append(d["content"])
            if c.get("finish_reason"):
                finish = c["finish_reason"]
    return {"model": model, "finish_reason": finish,
            "content_present": bool("".join(content).strip())}


# --- the test ---------------------------------------------------------------

CLIENTS = [
    ("urllib", _get_urllib, _post_urllib),
    ("httpx",  _get_httpx,  _post_httpx),
    ("curl",   _get_curl,   _post_curl),
]


def _by_client(per_client):
    return {n: v for n, v in per_client}


def test_cross_client_v1_endpoints_return_identical_canonical_forms(runner_subprocess, ollama_available):
    base, token = runner_subprocess["base"], runner_subprocess["token"]

    # /v1/health
    health = []
    for name, get_fn, _ in CLIENTS:
        status, body = get_fn(base, token, "/v1/health")
        assert status == 200, f"{name}: /v1/health expected 200, got {status}: {body!r}"
        health.append((name, _canon_health(body)))
    canon_set = {json.dumps(c, sort_keys=True) for _, c in health}
    assert len(canon_set) == 1, (
        f"/v1/health canonical forms diverge across clients: {dict(health)!r}"
    )

    # /v1/models
    models = []
    for name, get_fn, _ in CLIENTS:
        status, body = get_fn(base, token, "/v1/models")
        assert status == 200, f"{name}: /v1/models expected 200, got {status}: {body!r}"
        models.append((name, _canon_models(body)))
    canon_set = {json.dumps(c) for _, c in models}
    assert len(canon_set) == 1, (
        f"/v1/models canonical forms diverge across clients: {dict(models)!r}"
    )

    # /v1/chat/completions non-streaming
    chat_body = {
        "model": ollama_available, "stream": False, "max_tokens": 6,
        "messages": [{"role": "user", "content": "Hi."}],
    }
    chats = []
    for name, _, post_fn in CLIENTS:
        status, body = post_fn(base, token, "/v1/chat/completions", chat_body, stream=False)
        assert status == 200, f"{name}: chat-non-stream expected 200, got {status}: {body!r}"
        chats.append((name, _canon_chat_nostream(body)))
    canon_set = {json.dumps(c, sort_keys=True) for _, c in chats}
    assert len(canon_set) == 1, (
        f"/v1/chat/completions non-stream canonical forms diverge: {dict(chats)!r}"
    )

    # /v1/chat/completions streaming
    chat_body_stream = {
        "model": ollama_available, "stream": True, "max_tokens": 6,
        "messages": [{"role": "user", "content": "Hi."}],
    }
    streams = []
    for name, _, post_fn in CLIENTS:
        status, text = post_fn(base, token, "/v1/chat/completions", chat_body_stream, stream=True)
        assert status == 200, f"{name}: chat-stream expected 200, got {status}: text={text[:200]!r}"
        streams.append((name, _canon_chat_stream(text)))
    canon_set = {json.dumps(c, sort_keys=True) for _, c in streams}
    assert len(canon_set) == 1, (
        f"/v1/chat/completions streaming canonical forms diverge: {dict(streams)!r}"
    )
