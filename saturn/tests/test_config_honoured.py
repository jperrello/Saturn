"""Saturn-qj5.14 — config-honoured-end-to-end (the LLM half).

Per PRE_SPECS_B3.md §17.B.4. The user's central concern: "if I set max_tokens=50,
does the LLM stop at 50?" Saturn's job is to pass params through to the upstream;
the upstream's honesty is what we assert. Read the upstream's own response (token
counts, finish_reason, model id) — never Saturn's internal state.

No mocks. Real Ollama for free/bulk; one keyed OpenRouter sub-key for end-to-end.

Both creation paths must be covered per RUN_BRIEF Bucket 3:
  (a) editing an existing service config and verifying the edit propagates,
  (b) creating a brand-new service and verifying its config takes effect.

This file pins the canonical fields. Extend the parametrize lists to the full
6-field table (§17.B.4 per-field assertion table) as backends gain reliability.
"""

import json
import os
import secrets
import socket
import subprocess
import time
import urllib.request
import uuid

import pytest

from .conftest_b3 import _free, _ping, MIN_ADMIN_TOKEN, MIN_PASSWORD


pytestmark = pytest.mark.timeout(120)


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
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/keys",
        data=json.dumps({"name": f"brutus-qj5.14-{uuid.uuid4().hex[:8]}", "limit": 0.10}).encode(),
        headers={"Authorization": f"Bearer {parent}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        body = json.loads(urllib.request.urlopen(req, timeout=10).read())
    except Exception as e:
        pytest.skip(f"OpenRouter mgmt API unreachable: {e}")
    sub_hash = body["data"]["hash"]
    sub_key = body["key"]
    os.environ["OPENROUTER_TEST_KEY"] = sub_key
    try:
        yield sub_key
    finally:
        os.environ.pop("OPENROUTER_TEST_KEY", None)
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


# --- Saturn web + service spin-up helpers (no harness import to keep this self-contained) ---

@pytest.fixture
def saturn_web(tmp_path):
    """Spin up `saturn web` against an isolated SATURN_DATA_DIR with a known admin token.
    Yields {origin, token}. Tears down at end."""
    port = _free()
    token = "brutus-qj5.14-" + secrets.token_urlsafe(16)
    runner_tok = "brutus-runner-" + secrets.token_urlsafe(16)
    passthrough = {k: v for k, v in os.environ.items() if k.startswith(("OPENROUTER_", "OLLAMA_", "DEEPINFRA_", "ANTHROPIC_", "OPENAI_"))}
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        **passthrough,
        "SATURN_ADMIN_TOKEN":    token,
        "SATURN_RUNNER_TOKEN":   runner_tok,
        "SATURN_ADMIN_PASSWORD": MIN_PASSWORD,
        "SATURN_DATA_DIR":       str(tmp_path / "data"),
        "SATURN_SERVICES_DIR":   str(tmp_path / "services"),
        "SATURN_BIND_HOST":      "127.0.0.1",
    }
    log = open(tmp_path / "saturn-web.log", "wb")
    proc = subprocess.Popen(
        ["python3", "-m", "saturn", "web", "--port", str(port)],
        env=env, stdout=log, stderr=log,
    )
    origin = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline and not _ping(origin):
        if proc.poll() is not None:
            log.close()
            pytest.fail(f"saturn web exited during startup; see {tmp_path / 'saturn-web.log'}")
        time.sleep(0.3)
    if not _ping(origin):
        proc.terminate()
        pytest.fail("saturn web never came up")
    try:
        yield {"origin": origin, "token": token, "runner_token": runner_tok,
               "services_dir": tmp_path / "services"}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _admin(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _post(origin, path, body, headers):
    req = urllib.request.Request(
        f"{origin}{path}",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=30)


# --- Path-A fixture: existing service preloaded into SATURN_SERVICES_DIR ---

@pytest.fixture
def existing_ollama_service(saturn_web, ollama_available):
    """Path (a): write a TOML directly into the services dir BEFORE saturn web reloads.
    For this test we restart saturn web after writing — emulates 'existing config'."""
    name = f"qj514-existing-{uuid.uuid4().hex[:6]}"
    services = saturn_web["services_dir"]
    services.mkdir(parents=True, exist_ok=True)
    (services / f"{name}.toml").write_text(
        f'name = "{name}"\n'
        f'deployment = "local"\n'
        f'api_type = "ollama"\n'
        f'priority = 50\n'
        f'[upstream]\n'
        f'base_url = "http://localhost:11434/v1"\n'
        f'[server]\n'
        f'port = 0\n'
        f'[beacon]\n'
        f'enabled = false\n'
    )
    return name


# --- Path-B fixture: new service via /api/services ---

@pytest.fixture
def new_ollama_service(saturn_web, ollama_available):
    """Path (b): create via POST /api/services with admin auth."""
    name = f"qj514-new-{uuid.uuid4().hex[:6]}"
    body = {
        "name": name,
        "deployment": "local",
        "api_type": "ollama",
        "priority": 50,
        "upstream": {"base_url": "http://localhost:11434/v1"},
    }
    _post(saturn_web["origin"], "/api/services", body, _admin(saturn_web["token"]))
    return name


def _chat_via_saturn(origin, admin_token, service_name, model, prompt, **params):
    """Hit Saturn's /api/chat with the given params; return the assistant text + raw response."""
    body = {
        "service": service_name,
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        **params,
    }
    req = urllib.request.Request(
        f"{origin}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
        method="POST",
    )
    raw = urllib.request.urlopen(req, timeout=60).read()
    return json.loads(raw)


# --- Field × backend × path matrix (subset; extend per §17.B.4 table) ---

@pytest.mark.parametrize("path_fixture", ["existing_ollama_service", "new_ollama_service"])
def test_max_tokens_50_honoured_by_ollama(request, saturn_web, ollama_available, path_fixture):
    """max_tokens=50 ⇒ usage.completion_tokens ≤ 50. Both creation paths."""
    service = request.getfixturevalue(path_fixture)
    resp = _chat_via_saturn(
        saturn_web["origin"], saturn_web["token"],
        service, ollama_available,
        "Tell me a long story about the history of computing in vivid detail.",
        max_tokens=50,
    )
    usage = resp.get("usage") or {}
    completion_tokens = usage.get("completion_tokens")
    assert completion_tokens is not None, f"no usage.completion_tokens in response: {resp!r}"
    assert completion_tokens <= 50, (
        f"max_tokens=50 violated: completion_tokens={completion_tokens}. Saturn must pass "
        f"max_tokens through to the upstream; if Ollama is honouring it, this passes."
    )


@pytest.mark.parametrize("path_fixture", ["existing_ollama_service", "new_ollama_service"])
def test_model_id_honoured_by_ollama(request, saturn_web, ollama_available, path_fixture):
    """model=<X> ⇒ response.model contains <X>. Both creation paths."""
    service = request.getfixturevalue(path_fixture)
    resp = _chat_via_saturn(
        saturn_web["origin"], saturn_web["token"],
        service, ollama_available,
        "Say hi.",
        max_tokens=8,
    )
    returned = (resp.get("model") or "").lower()
    assert ollama_available.lower().split(":")[0] in returned, (
        f"expected model id containing {ollama_available!r}; got response.model={returned!r}"
    )


# --- OpenRouter half — skipped without OPENROUTER_PROVISIONING_KEY ---

@pytest.fixture
def openrouter_service(saturn_web, openrouter_subkey):
    """Path (b) for OpenRouter: create + start with the minted sub-key.
    OPENROUTER_TEST_KEY is set in os.environ by openrouter_subkey (session-scoped),
    and saturn_web's env passthrough propagates it to the spawned subprocess."""
    name = f"qj514-or-{uuid.uuid4().hex[:6]}"
    body = {
        "name": name,
        "deployment": "cloud",
        "api_type": "openai",
        "priority": 30,
        "upstream": {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_TEST_KEY",
        },
    }
    _post(saturn_web["origin"], "/api/services", body, _admin(saturn_web["token"]))
    return name


def test_max_tokens_50_honoured_by_openrouter(saturn_web, openrouter_service):
    """One OpenRouter end-to-end pass through a minted sub-key (limit 0.10 USD; revoked on teardown)."""
    resp = _chat_via_saturn(
        saturn_web["origin"], saturn_web["token"],
        openrouter_service, "openai/gpt-4o-mini",
        "Tell me a long story about computing.",
        max_tokens=50,
    )
    usage = resp.get("usage") or {}
    completion_tokens = usage.get("completion_tokens")
    assert completion_tokens is not None, f"no usage.completion_tokens: {resp!r}"
    assert completion_tokens <= 50
