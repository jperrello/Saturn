"""Saturn-8v5 — auth bypass via config.server.module.

qj5.16.1 added bearer auth on /v1/* but only on the inline ServiceRunner.create_app() path.
When config.server.module is set (saturn/runner.py:481), the runner imports the module and
uses mod.app verbatim, skipping the auth wrapper. saturn/servers/{ollama,claude,fallback}.py
all expose /v1/health, /v1/models, /v1/chat/completions with no auth.

Contract: regardless of whether config.server.module is set, the FastAPI app produced for a
ServiceRunner must require bearer auth on every /v1/* endpoint.
"""

import pytest

from saturn.config import ServiceConfig, UpstreamConfig, ServerConfig


TOKEN = "brutus-8v5-fixture-token"


@pytest.fixture
def env_token(monkeypatch):
    monkeypatch.setenv("SATURN_RUNNER_TOKEN", TOKEN)


def _module_config(name="t-mod"):
    return ServiceConfig(
        name=name,
        deployment="network",
        upstream=UpstreamConfig(base_url=""),
        server=ServerConfig(module="saturn.servers.fallback", port=0),
    )


def _inline_config(name="t-inline"):
    return ServiceConfig(
        name=name,
        deployment="network",
        upstream=UpstreamConfig(base_url="http://localhost:99999"),
    )


def _build(config):
    """Single dispatch point that the implementer's fix must populate.

    Required: saturn.runner.build_app(config: ServiceConfig) -> FastAPI
      - For config.server.module: import the module and wrap mod.app with the same
        bearer-auth dependency that ServiceRunner.create_app() uses.
      - For inline runners: equivalent to ServiceRunner(config).create_app().

    The test refuses to hand-roll the dispatch — that is exactly the bug shape.
    """
    from saturn.runner import build_app
    return build_app(config)


def _client(app):
    from fastapi.testclient import TestClient
    return TestClient(app)


# --- Inline path: regression guard for qj5.16.1 ---

def test_inline_runner_still_requires_auth(env_token):
    app = _build(_inline_config())
    with _client(app) as c:
        assert c.get("/v1/health").status_code == 401


# --- server.module path: the 8v5 bug ---

@pytest.mark.parametrize("module", [
    "saturn.servers.fallback",
    "saturn.servers.ollama",
    "saturn.servers.claude",
])
def test_server_module_app_health_requires_auth(env_token, module):
    cfg = ServiceConfig(
        name="m",
        deployment="network",
        upstream=UpstreamConfig(base_url=""),
        server=ServerConfig(module=module, port=0),
    )
    app = _build(cfg)
    with _client(app) as c:
        r = c.get("/v1/health")
        assert r.status_code == 401, (
            f"server.module={module!r} bypassed auth on /v1/health: got {r.status_code}"
        )


@pytest.mark.parametrize("module", [
    "saturn.servers.fallback",
    "saturn.servers.ollama",
    "saturn.servers.claude",
])
def test_server_module_app_models_requires_auth(env_token, module):
    cfg = ServiceConfig(
        name="m",
        deployment="network",
        upstream=UpstreamConfig(base_url=""),
        server=ServerConfig(module=module, port=0),
    )
    app = _build(cfg)
    with _client(app) as c:
        assert c.get("/v1/models").status_code == 401


@pytest.mark.parametrize("module", [
    "saturn.servers.fallback",
    "saturn.servers.ollama",
    "saturn.servers.claude",
])
def test_server_module_app_chat_completions_requires_auth(env_token, module):
    cfg = ServiceConfig(
        name="m",
        deployment="network",
        upstream=UpstreamConfig(base_url=""),
        server=ServerConfig(module=module, port=0),
    )
    app = _build(cfg)
    with _client(app) as c:
        r = c.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 401


def test_server_module_app_wrong_token_rejects(env_token):
    app = _build(_module_config())
    with _client(app) as c:
        assert c.get("/v1/health", headers={"Authorization": "Bearer WRONG"}).status_code == 401


def test_server_module_app_correct_token_passes(env_token):
    """Use saturn.servers.fallback — its /v1/health returns 200 unconditionally (no daemon dep)."""
    app = _build(_module_config())
    with _client(app) as c:
        r = c.get("/v1/health", headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200, f"correct bearer must reach handler, got {r.status_code}"
        assert r.json().get("saturn") is True
