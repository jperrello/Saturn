import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
TOKEN = "test-fallback-token-tqm"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait(port, path="/v1/health", timeout=15.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}{path}", headers=AUTH, timeout=1.0)
            if r.status_code < 500:
                return r
        except Exception as e:
            last = e
        time.sleep(0.2)
    raise RuntimeError(f"server :{port} never came up: {last}")


@pytest.fixture
def saturn_fallback():
    port = _free()
    env = dict(os.environ)
    env["SATURN_RUNNER_TOKEN"] = TOKEN
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(
        [sys.executable, "-m", "saturn", "run", "fallback",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(REPO), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        _wait(port, "/v1/health", timeout=20.0)
    except Exception:
        try:
            out, err = p.communicate(timeout=2.0)
        except Exception:
            p.kill()
            out, err = p.communicate()
        raise AssertionError(f"saturn run fallback failed.\nstdout={out!r}\nstderr={err!r}")
    yield port
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=3.0)
        except Exception:
            p.kill()
            p.wait(timeout=3.0)


def test_fallback_profile_shipped():
    f = REPO / "saturn" / "services" / "fallback.toml"
    assert f.exists()
    text = f.read_text()
    assert 'name = "fallback"' in text
    assert 'priority = 99' in text
    assert 'api_type = "openai"' in text


def test_fallback_module_importable():
    import importlib
    mod = importlib.import_module("saturn.servers.fallback")
    assert hasattr(mod, "app")
    assert hasattr(mod, "RESPONSES") and len(mod.RESPONSES) > 0


def test_fallback_config_loadable():
    from saturn.config import load_service_config
    cfg = load_service_config("fallback")
    assert cfg is not None
    assert cfg.api_type == "openai"
    assert cfg.priority == 99


def test_fallback_health_ok(saturn_fallback):
    r = httpx.get(f"http://127.0.0.1:{saturn_fallback}/v1/health", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("provider") == "Fallback"


def test_fallback_models_lists_dont_pick_me(saturn_fallback):
    r = httpx.get(f"http://127.0.0.1:{saturn_fallback}/v1/models", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text
    ids = [m["id"] for m in r.json()["data"]]
    assert "dont_pick_me" in ids


def test_fallback_chat_returns_curated_quip(saturn_fallback):
    r = httpx.post(
        f"http://127.0.0.1:{saturn_fallback}/v1/chat/completions",
        json={"model": "dont_pick_me", "messages": [{"role": "user", "content": "hi"}]},
        headers=AUTH, timeout=5.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    text = body["choices"][0]["message"]["content"]
    from saturn.servers.fallback import RESPONSES
    assert text in RESPONSES, f"unexpected fallback text: {text!r}"


def test_fallback_chat_rejects_unknown_model(saturn_fallback):
    r = httpx.post(
        f"http://127.0.0.1:{saturn_fallback}/v1/chat/completions",
        json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        headers=AUTH, timeout=5.0,
    )
    assert r.status_code == 400, r.text


def test_fallback_advertises_priority_99(saturn_fallback):
    from saturn.discovery import discover
    services = discover(timeout=5.0)
    mine = [s for s in services if s.port == saturn_fallback]
    assert mine, f"fallback not advertised: {[(s.name, s.port) for s in services]}"
    assert mine[0].priority == 99
    assert mine[0].api_type == "openai"
