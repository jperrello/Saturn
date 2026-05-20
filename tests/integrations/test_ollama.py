import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
TOKEN = "test-ollama-token-ys8"
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


def _ollama_up():
    try:
        r = httpx.get("http://localhost:11434/api/version", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_models():
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if r.status_code != 200:
            return []
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


live = pytest.mark.skipif(not _ollama_up(), reason="ollama daemon not running on localhost:11434")


@pytest.fixture
def saturn_ollama():
    sport = _free()
    env = dict(os.environ)
    env["SATURN_RUNNER_TOKEN"] = TOKEN
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(
        [sys.executable, "-m", "saturn", "run", "ollama",
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
        raise AssertionError(f"saturn run ollama failed.\nstdout={out!r}\nstderr={err!r}")
    yield sport
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=3.0)
        except Exception:
            p.kill()
            p.wait(timeout=3.0)


def test_ollama_profile_shipped():
    f = REPO / "saturn" / "services" / "ollama.toml"
    assert f.exists()
    text = f.read_text()
    assert 'name = "ollama"' in text
    assert 'api_type = "ollama"' in text
    assert "11434" in text


def test_ollama_module_importable():
    import importlib
    mod = importlib.import_module("saturn.servers.ollama")
    assert hasattr(mod, "app")
    assert mod.OLLAMA_BASE_URL.endswith("11434")


def test_ollama_config_loadable():
    from saturn.config import load_service_config
    cfg = load_service_config("ollama")
    assert cfg is not None
    assert cfg.api_type == "ollama"


def test_ollama_health_503_when_daemon_down():
    from fastapi.testclient import TestClient
    from saturn.servers.ollama import app
    import saturn.servers.ollama as omod
    saved = omod.OLLAMA_BASE_URL
    omod.OLLAMA_BASE_URL = "http://127.0.0.1:1"
    try:
        c = TestClient(app)
        r = c.get("/v1/health")
        assert r.status_code == 503, r.text
    finally:
        omod.OLLAMA_BASE_URL = saved


@live
def test_ollama_health_ok(saturn_ollama):
    r = httpx.get(f"http://127.0.0.1:{saturn_ollama}/v1/health", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("provider") == "Ollama"


@live
def test_ollama_models_proxied(saturn_ollama):
    r = httpx.get(f"http://127.0.0.1:{saturn_ollama}/v1/models", headers=AUTH, timeout=5.0)
    assert r.status_code == 200, r.text
    ids = [m["id"] for m in r.json()["data"]]
    upstream = _ollama_models()
    assert upstream, "no models in real ollama daemon"
    for name in upstream:
        assert name in ids, f"upstream model {name!r} not proxied through Saturn: {ids}"


@live
def test_ollama_chat_translated(saturn_ollama):
    models = _ollama_models()
    if not models:
        pytest.skip("no ollama models pulled")
    model = models[0]
    r = httpx.post(
        f"http://127.0.0.1:{saturn_ollama}/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": "say only the word OK"}]},
        headers=AUTH, timeout=60.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    msg = body["choices"][0]["message"]
    assert msg["role"] == "assistant"
    assert isinstance(msg.get("content"), str) and msg["content"]
    assert "usage" in body
    assert body["usage"]["total_tokens"] >= 1


@live
def test_ollama_advertises_ollama_apitype(saturn_ollama):
    from saturn.discovery import discover
    services = discover(timeout=5.0)
    mine = [s for s in services if s.port == saturn_ollama]
    assert mine, f"ollama not advertised: {[(s.name, s.port) for s in services]}"
    assert mine[0].api_type == "ollama"
