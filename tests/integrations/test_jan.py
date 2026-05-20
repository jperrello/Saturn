import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
TOKEN = "test-jan-token-7uv"
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


def test_jan_audit_doc_shipped():
    f = REPO / "docs" / "audit" / "jan.md"
    assert f.exists()
    text = f.read_text()
    assert "localStorage" in text
    assert "model-provider" in text
    assert "base_url" in text
    assert "useModelProvider" in text or "providers.ts" in text


def test_jan_research_factsheet_shipped():
    f = REPO / "dist" / "research" / "repos" / "jan.md"
    assert f.exists()
    text = f.read_text()
    assert "Jan" in text or "jan" in text
    assert "0.7" in text


def test_jan_documented_provider_entry_shape_serializable(saturn_endpoint):
    entry = {
        "active": True,
        "api_key": "",
        "base_url": saturn_endpoint,
        "provider": "saturn",
        "explore_models_url": "",
        "settings": [
            {"key": "api-key", "title": "API Key",
             "controller_type": "input",
             "controller_props": {"value": "", "type": "password"}},
            {"key": "base-url", "title": "Base URL",
             "controller_type": "input",
             "controller_props": {"value": saturn_endpoint}},
        ],
        "models": [],
    }
    s = json.dumps(entry)
    re = json.loads(s)
    assert re["base_url"] == saturn_endpoint
    assert re["base_url"].endswith("/v1")
    assert re["settings"][1]["controller_props"]["value"] == saturn_endpoint
    assert re["settings"][1]["controller_props"]["value"] == re["base_url"], \
        "doc requires settings[].controller_props.value to mirror base_url"


def test_jan_audit_calls_out_localstorage_persistence_quirk():
    text = (REPO / "docs" / "audit" / "jan.md").read_text()
    assert "localStorage" in text
    assert "zustand" in text or "persist" in text


def test_jan_saturn_endpoint_serves_models(saturn_endpoint):
    r = httpx.get(f"{saturn_endpoint}/models", headers=AUTH, timeout=3.0)
    assert r.status_code == 200
    body = r.json()
    assert body.get("object") == "list"
    assert isinstance(body.get("data"), list)


def test_jan_no_snippet_command_yet():
    r = subprocess.run(
        [sys.executable, "-m", "saturn", "jan-snippet", "--help"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    assert r.returncode != 0, "jan-snippet not yet implemented; remove this when contract lands"
