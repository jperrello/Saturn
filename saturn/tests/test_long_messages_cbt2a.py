"""Saturn-cbt.2.a — long-message HTTP-level regression for chat UX hardening.

Brutus contract per RUN_BRIEF_MAY05.md §A.2 first sub-feature:
  "Long messages (>4k tokens, >32k tokens) — UI doesn't freeze; receipt still arrives."

UI-freeze proper requires Playwright/Bombadil — that is cbt.2.a.ui (separate
sub-bead). This contract covers the HTTP-side proxy for "doesn't freeze":
saturn web MUST stream early and not buffer the entire upstream response.

Falsifiable bullets:

  1. /api/chat accepts a >4k-token user message and returns 200.
  2. Time-to-first-SSE-data-line (TTFB) MUST be < 5s — proves saturn web is
     streaming, not buffering. (UI freeze in real browsers is caused by
     server-side buffering of the whole response.)
  3. saturn_meta still arrives in the final SSE chunk with applied.usage
     populated, AND configured.model echoes the requested model.

NO MOCKS. Real Saturn web + real Ollama.
"""

import json
import os
import secrets
import socket
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(180)


@pytest.fixture
def saturn_web(tmp_path):
    port = _free()
    token = "brutus-cbt2a-" + secrets.token_urlsafe(16)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "SATURN_ADMIN_TOKEN":    token,
        "SATURN_RUNNER_TOKEN":   "brutus-runner-" + secrets.token_urlsafe(32),
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
        yield {"origin": origin, "token": token, "services_dir": tmp_path / "services"}
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()


@pytest.fixture(scope="session")
def ollama_available():
    if not _ping("http://localhost:11434/api/tags"):
        pytest.skip("Ollama not running")
    return "qwen2.5:0.5b"


@pytest.fixture
def ollama_service(saturn_web, ollama_available):
    name = f"cbt2a-{uuid.uuid4().hex[:6]}"
    sd = saturn_web["services_dir"]
    sd.mkdir(parents=True, exist_ok=True)
    (sd / f"{name}.toml").write_text(
        f'name = "{name}"\n'
        f'deployment = "local"\n'
        f'api_type = "ollama"\n'
        f'priority = 50\n'
        f'[upstream]\nbase_url = "http://localhost:11434/v1"\n'
        f'[server]\nport = 0\n'
        f'[beacon]\nenabled = false\n'
    )
    return name


def _last_meta(text):
    for line in reversed(text.splitlines()):
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
        "no saturn_meta on /api/chat under long-message load; UI receipt regressed. "
        "Stream tail:\n" + text[-1500:]
    )


def _stream_with_ttfb(origin, token, body, req_timeout=120):
    """POST /api/chat and return (ttfb_seconds, full_text). TTFB measured as
    seconds until first non-empty SSE 'data:' line is read."""
    req = urllib.request.Request(
        f"{origin}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    chunks = []
    ttfb = None
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=req_timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace")
            chunks.append(line)
            if ttfb is None:
                stripped = line.strip()
                if stripped.startswith("data:") and stripped not in ("data:", "data: ", "data: [DONE]"):
                    ttfb = time.time() - t0
    if ttfb is None:
        ttfb = time.time() - t0
    return ttfb, "".join(chunks)


def test_long_message_4k_tokens_streams_promptly_and_keeps_receipt(saturn_web, ollama_service, ollama_available):
    # ~4k tokens ≈ 16k chars. Build a deterministic long input.
    long_user = ("the quick brown fox jumps over the lazy dog. " * 360).strip()
    assert len(long_user) >= 16000, f"setup error: long_user too short ({len(long_user)} chars)"

    body = {
        "service": ollama_service,
        "model": ollama_available,
        "stream": True,
        "max_tokens": 8,
        "messages": [
            {"role": "system", "content": "Reply with one short word."},
            {"role": "user", "content": long_user},
        ],
    }

    ttfb, text = _stream_with_ttfb(saturn_web["origin"], saturn_web["token"], body)

    assert ttfb < 5.0, (
        f"time-to-first-SSE-chunk for a >4k-token user message must be <5s "
        f"(server-side buffering causes the UI freeze symptom); measured {ttfb:.2f}s"
    )

    meta = _last_meta(text)
    assert meta.get("schema_version") == 1, f"saturn_meta schema regressed: {meta!r}"
    applied = meta.get("applied") or {}
    usage = applied.get("usage") or {}
    assert usage.get("prompt_tokens", 0) >= 1000, (
        f"applied.usage.prompt_tokens must reflect the large input; "
        f"got usage={usage!r}"
    )
    assert (meta.get("configured") or {}).get("model") == ollama_available, (
        f"configured.model must echo requested model under long-input load; "
        f"got configured={meta.get('configured')!r}"
    )
