import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
TOKEN = "test-aider-token-bks"
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


def test_aider_audit_doc_shipped():
    f = REPO / "docs" / "audit" / "aider.md"
    assert f.exists()
    text = f.read_text()
    assert "--openai-api-base" in text
    assert "OPENAI_API_BASE" in text
    assert ".aider.conf.yml" in text


def test_aider_research_factsheet_shipped():
    f = REPO / "dist" / "research" / "repos" / "aider.md"
    assert f.exists()
    text = f.read_text()
    assert "Aider" in text
    assert "0.86" in text


def test_aider_saturn_launcher_module_importable():
    import importlib
    mod = importlib.import_module("saturn.aider_saturn")
    assert hasattr(mod, "main")
    assert hasattr(mod, "fetch_models")
    assert hasattr(mod, "select_model")


def test_aider_saturn_launcher_help_runs():
    r = subprocess.run(
        [sys.executable, "-m", "saturn", "aider", "--help"],
        cwd=str(REPO), capture_output=True, text=True, timeout=10.0,
    )
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "--saturn-needs" in out
    assert "--saturn-min-context" in out
    assert "--saturn-prefer-free" in out


def test_aider_console_script_declared():
    pyproject = (REPO / "pyproject.toml").read_text()
    assert "aider-saturn" in pyproject
    assert "saturn.aider_saturn:main" in pyproject


def test_aider_env_var_shape_compatible_with_saturn(saturn_endpoint):
    assert saturn_endpoint.endswith("/v1")
    env = {"OPENAI_API_BASE": saturn_endpoint, "OPENAI_API_KEY": "saturn-dummy"}
    r = httpx.get(f"{env['OPENAI_API_BASE']}/health", headers=AUTH, timeout=3.0)
    assert r.status_code == 200


def test_aider_saturn_models_endpoint_round_trip(saturn_endpoint):
    r = httpx.get(f"{saturn_endpoint}/models", headers=AUTH, timeout=3.0)
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [m["id"] for m in body.get("data", [])]
    assert "dont_pick_me" in ids, "saturn endpoint must surface a /v1/models list aider can read via OPENAI_API_BASE"
