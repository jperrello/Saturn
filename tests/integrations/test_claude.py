import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
TOKEN = "test-claude-token-9hn"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait(port, path, timeout=20.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}{path}", headers=AUTH, timeout=1.0)
            return r
        except Exception as e:
            last = e
        time.sleep(0.2)
    raise RuntimeError(f"server :{port} never came up: {last}")


@pytest.fixture
def saturn_claude():
    sport = _free()
    env = dict(os.environ)
    env["SATURN_RUNNER_TOKEN"] = TOKEN
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(
        [sys.executable, "-m", "saturn", "run", "claude",
         "--host", "127.0.0.1", "--port", str(sport)],
        cwd=str(REPO), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        _wait(sport, "/v1/health", timeout=20.0)
    except Exception:
        try:
            out, err = p.communicate(timeout=2.0)
        except Exception:
            p.kill()
            out, err = p.communicate()
        raise AssertionError(f"saturn run claude failed.\nstdout={out!r}\nstderr={err!r}")
    yield sport
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=3.0)
        except Exception:
            p.kill()
            p.wait(timeout=3.0)


def test_claude_profile_shipped():
    f = REPO / "saturn" / "services" / "claude.toml"
    assert f.exists()
    text = f.read_text()
    assert 'name = "claude"' in text
    assert 'api_type = "openai"' in text
    assert 'priority = 5' in text
    assert 'module = "saturn.servers.claude"' in text


def test_claude_module_importable():
    import importlib
    mod = importlib.import_module("saturn.servers.claude")
    assert hasattr(mod, "app")
    assert mod.MODEL_MAP == {
        "claude-code-opus": "opus",
        "claude-code-sonnet": "sonnet",
        "claude-code-haiku": "haiku",
    }


def test_claude_config_loadable():
    from saturn.config import load_service_config
    cfg = load_service_config("claude")
    assert cfg is not None
    assert cfg.api_type == "openai"
    assert cfg.priority == 5


def test_claude_pops_claudecode_env():
    import importlib, sys as _sys, os as _os
    _os.environ["CLAUDECODE"] = "1"
    if "saturn.servers.claude" in _sys.modules:
        del _sys.modules["saturn.servers.claude"]
    importlib.import_module("saturn.servers.claude")
    assert "CLAUDECODE" not in _os.environ, \
        "module import must pop CLAUDECODE so SDK-spawned claude CLI doesn't refuse"


def test_claude_health(saturn_claude):
    r = httpx.get(f"http://127.0.0.1:{saturn_claude}/v1/health", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "claude-code"
    assert body["deployment"] == "network"


def test_claude_models_lists_three(saturn_claude):
    r = httpx.get(f"http://127.0.0.1:{saturn_claude}/v1/models", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text
    ids = sorted(m["id"] for m in r.json()["data"])
    assert ids == ["claude-code-haiku", "claude-code-opus", "claude-code-sonnet"]


def test_claude_chat_rejects_unknown_model(saturn_claude):
    r = httpx.post(
        f"http://127.0.0.1:{saturn_claude}/v1/chat/completions",
        json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        headers=AUTH, timeout=5.0,
    )
    assert r.status_code == 400, r.text


def test_claude_chat_rejects_no_user_message(saturn_claude):
    r = httpx.post(
        f"http://127.0.0.1:{saturn_claude}/v1/chat/completions",
        json={"model": "claude-code-haiku", "messages": [{"role": "system", "content": "x"}]},
        headers=AUTH, timeout=5.0,
    )
    assert r.status_code == 400, r.text
    assert "user message" in r.text.lower() or "no user" in r.text.lower()


def test_claude_advertises_openai(saturn_claude):
    from saturn.discovery import discover
    services = discover(timeout=5.0)
    mine = [s for s in services if s.port == saturn_claude]
    assert mine, f"claude not advertised: {[(s.name, s.port) for s in services]}"
    assert mine[0].api_type == "openai"
    assert mine[0].priority == 5
