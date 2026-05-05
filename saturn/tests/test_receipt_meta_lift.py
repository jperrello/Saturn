"""Saturn-cbt.1 / qj5.15.2 — saturn_meta receipt lift to other chat surfaces.

Brutus contract. Per PRE_SPECS_B3.md §17.F: lift the qj5.15 saturn_meta
envelope from /api/chat to:

  1. POST /api/proxy/chat                    (saturn/web.py:880)
  2. ServiceRunner POST /v1/chat/completions (saturn/runner.py:495, streaming)
  3. ServiceRunner POST /v1/chat/completions (saturn/runner.py:495, non-streaming)

Each surface MUST return saturn_meta with:
  - schema_version == 1
  - applied dict carrying max_tokens, model, system_prompt_sha256
  - verifiability dict (may be empty if no unverifiable params requested)

NO MOCKS. Real Saturn web + real Ollama. Reuses fixtures from test_receipt_meta.
"""

import hashlib
import json
import os
import secrets
import subprocess
import time
import urllib.request
import uuid

import pytest

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(180)


@pytest.fixture
def saturn_web(tmp_path):
    port = _free()
    token = "brutus-cbt1-" + secrets.token_urlsafe(16)
    runner_tok = "brutus-runner-" + secrets.token_urlsafe(16)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "SATURN_ADMIN_TOKEN":    token,
        "SATURN_RUNNER_TOKEN":   runner_tok,
        "SATURN_ADMIN_PASSWORD": MIN_PASSWORD,
        "SATURN_DATA_DIR":       str(tmp_path / "data"),
        "SATURN_SERVICES_DIR":   str(tmp_path / "services"),
        "SATURN_BIND_HOST":      "127.0.0.1",
    }
    log = open(tmp_path / "saturn-web.log", "wb")
    proc = subprocess.Popen(
        ["python3", "-m", "saturn", "web", "--port", str(port)],
        env=env, stdout=log, stderr=log,
    )
    origin = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline and not _ping(origin):
        if proc.poll() is not None:
            log.close()
            pytest.fail(f"saturn web exited; see {tmp_path / 'saturn-web.log'}")
        time.sleep(0.3)
    if not _ping(origin):
        proc.terminate()
        pytest.fail("saturn web never came up")
    try:
        yield {"origin": origin, "token": token}
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()


@pytest.fixture(scope="session")
def ollama_available():
    if not _ping("http://localhost:11434/api/tags"):
        pytest.skip("Ollama not running")
    return "qwen2.5:0.5b"


def _last_meta(stream_text):
    for line in reversed(stream_text.splitlines()):
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if isinstance(obj, dict) and "saturn_meta" in obj:
            return obj["saturn_meta"]
    raise AssertionError(
        "no chunk in the SSE stream carried `saturn_meta`. Per §17.F.2 the "
        "final chunk before `data: [DONE]` must include saturn_meta. "
        "Stream tail:\n" + stream_text[-1500:]
    )


def _sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()


def _assert_envelope_shape(meta, expected_max_tokens, expected_requested_model, expected_sys_sha=None):
    assert meta.get("schema_version") == 1, (
        f"schema_version must be 1; got {meta.get('schema_version')!r} in {meta!r}"
    )
    applied = meta.get("applied") or {}
    assert applied.get("max_tokens") == expected_max_tokens, (
        f"applied.max_tokens must echo the request's max_tokens={expected_max_tokens}; "
        f"got applied={applied!r}"
    )
    assert "model" in applied and applied["model"], (
        f"applied.model must be sourced from upstream response; got applied={applied!r}"
    )
    if expected_sys_sha is not None:
        assert applied.get("system_prompt_sha256") == expected_sys_sha, (
            f"applied.system_prompt_sha256 must be SHA-256 of the system prompt; "
            f"got {applied.get('system_prompt_sha256')!r}"
        )
    assert "verifiability" in meta and isinstance(meta["verifiability"], dict), (
        f"verifiability dict required (may be empty); got {meta.get('verifiability')!r}"
    )
    assert "configured" in meta and meta["configured"].get("model") == expected_requested_model, (
        f"configured.model must echo requested model {expected_requested_model!r}; "
        f"got configured={meta.get('configured')!r}"
    )


# --- Surface 1: /api/proxy/chat ---

def test_proxy_chat_emits_saturn_meta(saturn_web, ollama_available):
    sysp = "you are brutus-test-proxy"
    body = {
        "base_url": "http://localhost:11434/v1",
        "model": ollama_available,
        "api_type": "openai",
        "max_tokens": 8,
        "messages": [
            {"role": "system", "content": sysp},
            {"role": "user", "content": "Hi."},
        ],
    }
    req = urllib.request.Request(
        f"{saturn_web['origin']}/api/proxy/chat",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {saturn_web['token']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    meta = _last_meta(text)
    _assert_envelope_shape(meta, 8, ollama_available, _sha256(sysp))


# --- Surface 2: ServiceRunner /v1/chat/completions (streaming) ---

def _runner_client(monkeypatch, token, ollama_base="http://localhost:11434/v1"):
    from fastapi.testclient import TestClient
    from saturn.config import ServiceConfig, UpstreamConfig
    from saturn.runner import ServiceRunner
    monkeypatch.setenv("SATURN_RUNNER_TOKEN", token)
    cfg = ServiceConfig(
        name=f"cbt1-runner-{uuid.uuid4().hex[:6]}",
        deployment="local",
        api_type="ollama",
        upstream=UpstreamConfig(base_url=ollama_base),
    )
    return TestClient(ServiceRunner(cfg).create_app())


def test_runner_v1_chat_streaming_emits_saturn_meta(monkeypatch, ollama_available):
    token = "brutus-runner-" + secrets.token_urlsafe(8)
    sysp = "you are brutus-test-runner-stream"
    sys_sha = _sha256(sysp)
    with _runner_client(monkeypatch, token) as c:
        r = c.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model": ollama_available,
                "stream": True,
                "max_tokens": 8,
                "messages": [
                    {"role": "system", "content": sysp},
                    {"role": "user", "content": "Hi."},
                ],
            },
        )
        assert r.status_code == 200, f"runner /v1/chat/completions returned {r.status_code}: {r.text[:400]}"
        meta = _last_meta(r.text)
        _assert_envelope_shape(meta, 8, ollama_available, sys_sha)


def test_runner_v1_chat_non_streaming_emits_saturn_meta(monkeypatch, ollama_available):
    token = "brutus-runner-" + secrets.token_urlsafe(8)
    sysp = "you are brutus-test-runner-nostream"
    sys_sha = _sha256(sysp)
    with _runner_client(monkeypatch, token) as c:
        r = c.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model": ollama_available,
                "stream": False,
                "max_tokens": 8,
                "messages": [
                    {"role": "system", "content": sysp},
                    {"role": "user", "content": "Hi."},
                ],
            },
        )
        assert r.status_code == 200, f"runner /v1/chat/completions returned {r.status_code}: {r.text[:400]}"
        data = r.json()
        assert "saturn_meta" in data, (
            "non-streaming /v1/chat/completions response MUST carry top-level "
            f"saturn_meta key per §17.F.2.3; got keys={list(data.keys())}"
        )
        _assert_envelope_shape(data["saturn_meta"], 8, ollama_available, sys_sha)
