"""Shared B3 fixtures for qj5.14 — Saturn web boot, Ollama, OpenRouter sub-keys.

Per PRE_SPECS_B3.md §17.B.4. No mocks.
"""

import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

import pytest


MIN_ADMIN_TOKEN = "x" * 32
MIN_RUNNER_TOKEN = "y" * 32
MIN_PASSWORD = "brutus-fixture-pw-min-12chars"


def _free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _ping(url, timeout=2):
    try:
        urllib.request.urlopen(url, timeout=timeout).read()
        return True
    except Exception:
        return False


def _boot(env=None, admin_cfg=None, wait_secs=2.0):
    """Spawn `python3 -m saturn web` with a custom env. Returns (exit_code_or_0, stderr_text).
    exit_code_or_0 == 0 if the process is still alive after wait_secs (= boot succeeded)."""
    port = _free()
    base = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "SATURN_DATA_DIR": f"/tmp/brutus-b3-{uuid.uuid4().hex}",
    }
    if env:
        base.update(env)
    proc = subprocess.Popen(
        ["python3", "-m", "saturn", "web", "--port", str(port)],
        env=base,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + wait_secs
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0, (proc.stderr.read() or b"").decode("utf-8", "replace")
    return proc.returncode, (proc.stderr.read() or b"").decode("utf-8", "replace")


@pytest.fixture
def boot():
    """Per-test: invoke _boot(env=..., admin_cfg=...) and return (code, stderr)."""
    return _boot


@pytest.fixture
def MIN_ENV():
    return {
        "SATURN_ADMIN_TOKEN":     MIN_ADMIN_TOKEN,
        "SATURN_RUNNER_TOKEN":    MIN_RUNNER_TOKEN,
        "SATURN_ADMIN_PASSWORD":  MIN_PASSWORD,
    }


@pytest.fixture(scope="session")
def ollama_available():
    if not _ping("http://localhost:11434/api/tags"):
        pytest.skip("Ollama not running")
    return "qwen2.5:0.5b"


@pytest.fixture(scope="session")
def openrouter_subkey():
    parent = os.environ.get("OPENROUTER_PROVISIONING_KEY")
    if not parent:
        pytest.skip("no OPENROUTER_PROVISIONING_KEY in env")
    import json
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/keys",
        data=json.dumps({"name": f"brutus-qj5.14-{uuid.uuid4().hex[:8]}", "limit": 0.10}).encode(),
        headers={"Authorization": f"Bearer {parent}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        pytest.skip(f"OpenRouter mgmt API unreachable: {e}")
    body = json.loads(resp)
    sub_hash = body["data"]["hash"]
    sub_key = body["key"]
    yield sub_key
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                f"https://openrouter.ai/api/v1/keys/{sub_hash}",
                headers={"Authorization": f"Bearer {parent}"},
                method="DELETE",
            ),
            timeout=10,
        ).read()
    except Exception:
        pass
