"""Saturn-qj5.15 — per-turn applied-config receipt (`saturn_meta` envelope).

Per PRE_SPECS_B3.md §17.C + CONFIG_RECEIPT_PATTERNS.md (gullivan).
Six invariants — one per anti-pattern from the patterns doc:

  17.C.4.1  Receipt is honest (applied.X read from upstream, not echoed from request).
  17.C.4.2  Coerced values flagged (silent substitution → diff.coerced entry).
  17.C.4.3  system_prompt fingerprinted, not inlined.
  17.C.4.4  Per-turn independence (every assistant turn has its own meta).
  17.C.4.5  schema_version pinned at 1.
  17.C.4.6  Verifiability honesty (top_p/stop labelled requested-not-verifiable / best-effort).

No mocks. Real Saturn web + real Ollama; OpenRouter sub-key for 17.C.4.2.
"""

import hashlib
import json
import os
import secrets
import subprocess
import time
import urllib.request
import uuid

import pytest

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(180)


# --- Saturn web fixture (self-contained — same shape as test_config_honoured.py) ---

@pytest.fixture
def saturn_web(tmp_path):
    port = _free()
    token = "brutus-qj5.15-" + secrets.token_urlsafe(16)
    runner_tok = "brutus-runner-" + secrets.token_urlsafe(16)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
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
            pytest.fail(f"saturn web exited; see {tmp_path / 'saturn-web.log'}")
        time.sleep(0.3)
    if not _ping(origin):
        proc.terminate()
        pytest.fail("saturn web never came up")
    try:
        yield {"origin": origin, "token": token, "services_dir": tmp_path / "services"}
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()


@pytest.fixture(scope="session")
def ollama_available():
    if not _ping("http://localhost:11434/api/tags"):
        pytest.skip("Ollama not running")
    return "qwen2.5:0.5b"


@pytest.fixture
def ollama_service(saturn_web, ollama_available):
    name = f"qj515-{uuid.uuid4().hex[:6]}"
    sd = saturn_web["services_dir"]
    sd.mkdir(parents=True, exist_ok=True)
    (sd / f"{name}.toml").write_text(
        f'name = "{name}"\n'
        f'deployment = "local"\n'
        f'api_type = "ollama"\n'
        f'priority = 50\n'
        f'[upstream]\nbase_url = "http://localhost:11434/v1"\n'
        f'[server]\nport = 0\n'
        f'[beacon]\nenabled = false\n'
    )
    return name


# --- Helpers ---

def _post_chat(origin, admin_token, service, model, prompt, system=None, stream=True, **params):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    body = {"service": service, "model": model, "messages": msgs, "stream": stream, **params}
    req = urllib.request.Request(
        f"{origin}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def _last_meta(stream_text):
    """Parse SSE, find the most recent chunk whose JSON has 'saturn_meta'. Return that dict or raise."""
    for line in reversed(stream_text.splitlines()):
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if isinstance(obj, dict) and "saturn_meta" in obj:
            return obj["saturn_meta"]
    raise AssertionError(
        "no chunk in the SSE stream carried `saturn_meta`. Per §17.C.1 the final usage "
        "chunk before `data: [DONE]` must include saturn_meta. Stream excerpt:\n"
        + stream_text[-1500:]
    )


def _completion_token_count(stream_text):
    """Best-effort: pick the latest usage object's completion_tokens."""
    for line in reversed(stream_text.splitlines()):
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        u = (obj or {}).get("usage")
        if isinstance(u, dict) and "completion_tokens" in u:
            return u["completion_tokens"]
    return None


def _sha256_hex(s):
    return hashlib.sha256(s.encode()).hexdigest()


# --- 17.C.4.1 honest receipt ---

def test_receipt_max_tokens_reflects_actual_completion(saturn_web, ollama_service, ollama_available):
    text = _post_chat(
        saturn_web["origin"], saturn_web["token"],
        ollama_service, ollama_available,
        "Write 10000 words about cheese.", max_tokens=50,
    )
    meta = _last_meta(text)
    assert meta["applied"]["max_tokens"] == 50, f"applied.max_tokens != 50: {meta['applied']!r}"
    assert meta["applied"]["finish_reason"] == "length", (
        f"finish_reason should be 'length' when max_tokens cap hit; got {meta['applied'].get('finish_reason')!r}"
    )
    ct = _completion_token_count(text)
    assert ct is not None and ct <= 50, f"upstream completion_tokens={ct}, expected ≤ 50"


def test_receipt_model_echoes_upstream_id(saturn_web, ollama_service, ollama_available):
    text = _post_chat(
        saturn_web["origin"], saturn_web["token"],
        ollama_service, ollama_available, "Hi.", max_tokens=5,
    )
    meta = _last_meta(text)
    applied_model = (meta["applied"]["model"] or "").lower()
    assert ollama_available.split(":")[0] in applied_model, (
        f"applied.model must be sourced from the upstream's response, not echoed from the request. "
        f"Got applied.model={applied_model!r}, configured.model={ollama_available!r}"
    )


# --- 17.C.4.3 system_prompt fingerprinted ---

def test_system_prompt_hashed_not_inlined(saturn_web, ollama_service, ollama_available):
    secret = "MAGICAL_PHRASE_8b3c2_brutus_must_not_leak_this"
    text = _post_chat(
        saturn_web["origin"], saturn_web["token"],
        ollama_service, ollama_available,
        "What did I just tell you?", system=secret, max_tokens=10,
    )
    meta = _last_meta(text)
    assert meta["applied"]["system_prompt_sha256"] == _sha256_hex(secret), (
        f"applied.system_prompt_sha256 must be SHA-256 of the system prompt; got "
        f"{meta['applied'].get('system_prompt_sha256')!r}"
    )
    preview = meta["applied"].get("system_prompt_preview", "")
    assert len(preview) <= 120, f"system_prompt_preview must be ≤ 120 chars, got {len(preview)}"
    full_meta_str = json.dumps(meta)
    assert secret not in full_meta_str, (
        f"the full system prompt {secret!r} must NEVER appear in the receipt. "
        f"Only sha256 + ≤120-char preview are allowed."
    )


# --- 17.C.4.4 per-turn independence ---

def test_per_turn_meta_independence(saturn_web, ollama_service, ollama_available):
    r1 = _post_chat(saturn_web["origin"], saturn_web["token"],
                    ollama_service, ollama_available, "A", max_tokens=10)
    r2 = _post_chat(saturn_web["origin"], saturn_web["token"],
                    ollama_service, ollama_available, "B", max_tokens=20)
    m1 = _last_meta(r1)
    m2 = _last_meta(r2)
    assert m1["applied"]["max_tokens"] == 10, f"turn1 max_tokens != 10: {m1['applied']!r}"
    assert m2["applied"]["max_tokens"] == 20, f"turn2 max_tokens != 20: {m2['applied']!r}"


# --- 17.C.4.5 schema_version pinned ---

def test_schema_version_present_and_pinned(saturn_web, ollama_service, ollama_available):
    text = _post_chat(saturn_web["origin"], saturn_web["token"],
                      ollama_service, ollama_available, "Hi.", max_tokens=5)
    meta = _last_meta(text)
    assert meta["schema_version"] == 1, (
        f"schema_version must be pinned at 1 (canary); got {meta.get('schema_version')!r}"
    )


# --- 17.C.4.6 verifiability honesty ---

def test_unverifiable_fields_are_marked(saturn_web, ollama_service, ollama_available):
    text = _post_chat(saturn_web["origin"], saturn_web["token"],
                      ollama_service, ollama_available, "Hi.",
                      max_tokens=5, top_p=0.01)
    meta = _last_meta(text)
    verif = meta.get("verifiability") or {}
    assert verif.get("top_p") == "requested-not-verifiable", (
        f"top_p must be labelled 'requested-not-verifiable' in verifiability; got {verif!r}"
    )


# --- 17.C.4.2 coerced values flagged (OpenRouter, skipped without key) ---

@pytest.fixture(scope="session")
def openrouter_subkey():
    parent = os.environ.get("OPENROUTER_PROVISIONING_KEY")
    if not parent:
        pytest.skip("no OPENROUTER_PROVISIONING_KEY in env")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/keys",
        data=json.dumps({"name": f"brutus-qj5.15-{uuid.uuid4().hex[:8]}", "limit": 0.10}).encode(),
        headers={"Authorization": f"Bearer {parent}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        body = json.loads(urllib.request.urlopen(req, timeout=10).read())
    except Exception as e:
        pytest.skip(f"OpenRouter mgmt API unreachable: {e}")
    sub_hash = body["data"]["hash"]
    yield body["key"]
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


def test_receipt_flags_silent_substitution(saturn_web, openrouter_subkey, monkeypatch):
    monkeypatch.setenv("OPENROUTER_TEST_KEY", openrouter_subkey)
    name = f"qj515-or-{uuid.uuid4().hex[:6]}"
    sd = saturn_web["services_dir"]
    sd.mkdir(parents=True, exist_ok=True)
    (sd / f"{name}.toml").write_text(
        f'name = "{name}"\n'
        f'deployment = "cloud"\n'
        f'api_type = "openai"\n'
        f'priority = 30\n'
        f'[upstream]\n'
        f'base_url = "https://openrouter.ai/api/v1"\n'
        f'api_key_env = "OPENROUTER_TEST_KEY"\n'
        f'[server]\nport = 0\n'
        f'[beacon]\nenabled = false\n'
    )
    fake = "openai/gpt-4o-mini-doesnotexist"
    text = _post_chat(saturn_web["origin"], saturn_web["token"],
                      name, fake, "Hi.", max_tokens=5, fallback_allowed=True)
    meta = _last_meta(text)
    assert meta["applied"]["model"] != fake, (
        f"OpenRouter routed away from {fake!r}; applied.model must reflect the substitute"
    )
    assert "model" in (meta.get("diff") or {}).get("coerced", []), (
        f"silent substitution must surface in diff.coerced; got diff={meta.get('diff')!r}"
    )
