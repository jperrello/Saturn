import inspect

import pytest

from saturn.config import ServiceConfig, UpstreamConfig
from saturn.runner import ServiceRunner, run_service


TOKEN = "brutus-fixture-token-do-not-leak"
WRONG = "brutus-fixture-token-WRONG"


def _runner_with_token(monkeypatch):
    monkeypatch.setenv("SATURN_RUNNER_TOKEN", TOKEN)
    cfg = ServiceConfig(
        name="auth-runner",
        deployment="network",
        upstream=UpstreamConfig(base_url="http://localhost:99999"),
    )
    return ServiceRunner(cfg)


def _client(runner):
    from fastapi.testclient import TestClient
    return TestClient(runner.create_app())


def test_health_401_without_auth(monkeypatch):
    runner = _runner_with_token(monkeypatch)
    with _client(runner) as c:
        assert c.get("/v1/health").status_code == 401


def test_models_401_without_auth(monkeypatch):
    runner = _runner_with_token(monkeypatch)
    with _client(runner) as c:
        assert c.get("/v1/models").status_code == 401


def test_chat_completions_401_without_auth(monkeypatch):
    runner = _runner_with_token(monkeypatch)
    with _client(runner) as c:
        r = c.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 401
        assert "bearer" in r.headers.get("www-authenticate", "").lower(), (
            "401 must advertise 'WWW-Authenticate: Bearer' per CONFIG_FIELDS.md §F"
        )


def test_health_401_with_wrong_token(monkeypatch):
    runner = _runner_with_token(monkeypatch)
    with _client(runner) as c:
        r = c.get("/v1/health", headers={"Authorization": f"Bearer {WRONG}"})
        assert r.status_code == 401


def test_correct_token_succeeds_and_wrong_token_rejects(monkeypatch):
    runner = _runner_with_token(monkeypatch)
    with _client(runner) as c:
        bad = c.get("/v1/health", headers={"Authorization": f"Bearer {WRONG}"})
        good = c.get("/v1/health", headers={"Authorization": f"Bearer {TOKEN}"})
    assert bad.status_code == 401
    assert good.status_code == 200
    assert good.json().get("saturn") is True


def test_run_service_default_bind_is_loopback():
    sig = inspect.signature(run_service)
    assert sig.parameters["host"].default == "127.0.0.1", (
        f"run_service default host must be 127.0.0.1 (loopback), "
        f"got {sig.parameters['host'].default!r}"
    )


def test_main_argparse_default_host_is_loopback():
    import argparse
    import saturn.runner as runner_mod

    src = inspect.getsource(runner_mod.main)
    assert '"--host"' in src and 'default="127.0.0.1"' in src, (
        "main() argparse must default --host to 127.0.0.1; "
        "0.0.0.0 must be explicit opt-in"
    )
