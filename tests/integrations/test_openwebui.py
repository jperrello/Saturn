import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
TOKEN = "test-owui-token-zgy"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait(port, path, timeout=15.0):
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
    raise RuntimeError(f"never came up: {last}")


@pytest.fixture
def saturn_endpoint():
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
        _wait(port, "/v1/health")
    except Exception:
        p.kill(); raise
    yield f"http://127.0.0.1:{port}/v1"
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=3.0)
        except Exception:
            p.kill()


def test_owui_audit_doc_shipped():
    f = REPO / "docs" / "audit" / "openwebui.md"
    assert f.exists()
    text = f.read_text()
    assert "OPENAI_API_BASE_URLS" in text
    assert "semicolon" in text.lower()
    assert "ENABLE_PERSISTENT_CONFIG" in text


def test_owui_research_factsheet_shipped():
    f = REPO / "dist" / "research" / "repos" / "owui.md"
    assert f.exists()
    text = f.read_text()
    assert "open-webui" in text
    assert "OPENAI_API_BASE_URL" in text or "open-webui serve" in text


def test_owui_documented_persistence_trap_in_doc():
    text = (REPO / "docs" / "audit" / "openwebui.md").read_text()
    assert "Persistence trap" in text
    assert "openai.api_base_urls" in text


def test_owui_env_var_shape_compatible_with_saturn(saturn_endpoint):
    assert saturn_endpoint.endswith("/v1")
    composed = f"{saturn_endpoint};https://api.openai.com/v1"
    assert composed.count(";") == 1
    parts = composed.split(";")
    assert parts[0] == saturn_endpoint
    r = httpx.get(f"{parts[0]}/health", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text


def test_owui_saturn_endpoint_serves_models_for_owui(saturn_endpoint):
    r = httpx.get(f"{saturn_endpoint}/models", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("object") == "list"
    assert isinstance(body.get("data"), list)


def test_owui_no_snippet_command_yet():
    r = subprocess.run(
        [sys.executable, "-m", "saturn", "openwebui-snippet", "--help"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    assert r.returncode != 0, "openwebui-snippet not yet implemented; remove this when contract lands"
