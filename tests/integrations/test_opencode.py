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
TOKEN = "test-opencode-token-3eg"
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


def test_opencode_audit_doc_shipped():
    f = REPO / "docs" / "audit" / "opencode.md"
    assert f.exists()
    text = f.read_text()
    assert "OPENCODE_CONFIG_DIR" in text
    assert "provider.<id>.options.baseURL" in text or "options.baseURL" in text
    assert "opencode.json" in text


def test_opencode_research_factsheet_shipped():
    f = REPO / "dist" / "research" / "repos" / "opencode.md"
    assert f.exists()
    text = f.read_text()
    assert "opencode" in text
    assert "install" in text.lower()


def test_opencode_no_env_var_override_documented():
    text = (REPO / "docs" / "audit" / "opencode.md").read_text()
    assert "no `OPENAI_BASE_URL`" in text or "no OPENAI_BASE_URL" in text \
        or "JSON config mutation" in text, \
        "audit must document that opencode requires JSON config (no env-var path)"


def test_opencode_documented_config_shape_is_valid_json(tmp_path, saturn_endpoint):
    config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "openai": {
                "options": {
                    "baseURL": saturn_endpoint,
                    "apiKey": "saturn-dummy",
                },
            },
        },
    }
    p = tmp_path / "opencode.json"
    p.write_text(json.dumps(config, indent=2))
    parsed = json.loads(p.read_text())
    assert parsed["provider"]["openai"]["options"]["baseURL"] == saturn_endpoint
    assert parsed["provider"]["openai"]["options"]["baseURL"].endswith("/v1")


def test_opencode_saturn_endpoint_serves_models(saturn_endpoint):
    r = httpx.get(f"{saturn_endpoint}/models", headers=AUTH, timeout=3.0)
    assert r.status_code == 200
    assert r.json().get("object") == "list"


def test_opencode_no_snippet_command_yet():
    r = subprocess.run(
        [sys.executable, "-m", "saturn", "opencode-snippet", "--help"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    assert r.returncode != 0, "opencode-snippet not yet implemented; remove this when contract lands"
