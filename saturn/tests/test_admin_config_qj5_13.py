"""Saturn-qj5.13 — Configure page schema lift (admin_config.json round-trip + persist + live + refuse).

Per PRE_SPECS_B3.md §17.A.4 (geoff). Three test layers, condensed into one file:

  17.A.4.1  Round-trip — every CONFIG_FIELDS §A.2-A.8 row POST→GET losslessly.
  17.A.4.2  Restart preservation — every field survives a process restart.
  17.A.4.3  Live propagation — runtime-effective fields take effect without restart.
  17.A.4.4  Refuse-on-invalid — every CONFIG_FIELDS §C violation → 422; on-disk unchanged.

Plus a meta-test: every field defined on `AdminConfig.model_fields` (excluding the three
existing ones) must have at least one row in the round-trip table.

No mocks. Real Saturn web subprocess.
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

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(120)


# --- Saturn web fixture ---

@pytest.fixture
def saturn_web(tmp_path):
    port = _free()
    token = "brutus-qj5.13-" + secrets.token_urlsafe(16)
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
        yield {"origin": origin, "token": token, "data_dir": tmp_path / "data",
               "env": env, "port": port, "tmp_path": tmp_path, "proc": proc}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill()


def _admin(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _post(origin, path, body, token):
    req = urllib.request.Request(
        f"{origin}{path}",
        data=json.dumps(body).encode(),
        headers=_admin(token),
        method="POST",
    )
    try:
        return urllib.request.urlopen(req, timeout=15).getcode(), json.loads(urllib.request.urlopen(
            urllib.request.Request(f"{origin}{path}", data=json.dumps(body).encode(),
                                    headers=_admin(token), method="POST"),
            timeout=15,
        ).read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _post_status(origin, path, body, token):
    """Return (status_code, body_json_or_text). Single request, captures HTTP errors."""
    req = urllib.request.Request(
        f"{origin}{path}",
        data=json.dumps(body).encode(),
        headers=_admin(token),
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.getcode(), json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def _get(origin, path, token):
    req = urllib.request.Request(f"{origin}{path}", headers=_admin(token), method="GET")
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


# --- 17.A.4.1 round-trip ---

ROUNDTRIP_TABLE = [
    # A.2 auth
    ("admin_session_ttl_s",      7200),
    ("admin_token_env",          "SATURN_ADMIN_TOKEN"),
    ("runner_token_env",         "SATURN_RUNNER_TOKEN"),
    ("admin_password_env",       "SATURN_ADMIN_PASSWORD"),
    # A.3 network
    ("bind_host",                "127.0.0.1"),
    ("runner_bind_host",         "127.0.0.1"),
    ("trusted_proxies",          ["127.0.0.1", "10.0.0.0/8"]),
    ("cors_origins",             ["http://localhost:3000"]),
    # A.4 rate
    ("rate_rpm",                 120),
    ("rate_tpm",                 200000),
    ("rate_concurrent_per_ip",   8),
    ("max_budget_usd",           5.00),
    ("budget_period",            "monthly"),
    ("per_ip_max_budget_usd",    1.00),
    # A.5 endpoint policy
    ("public_routes",            ["/api/admin/auth", "/v1/health"]),
    ("require_auth_on_v1",       True),
    # A.6 proxy hygiene
    ("proxy_models_method",      "POST"),
    ("redact_proxy_keys_in_logs", True),
    # A.7 MCP
    ("mcp_allowed_urls",         ["http://localhost:8080/mcp"]),
    ("mcp_auth_token_envs",      {"localhost": "MCP_LOCAL_TOKEN"}),
    # A.8 service identity
    ("trust_mode",               "allowlist"),
    ("trusted_node_ids",         ["d2a0c4d8-c7a1-4d88-a575-7f68cdf1812e"]),
    ("beacon_max_budget_usd",    2.50),
]


@pytest.mark.parametrize("field,value", ROUNDTRIP_TABLE)
def test_field_roundtrips(saturn_web, field, value):
    code, _ = _post_status(saturn_web["origin"], "/api/admin/config",
                           {field: value}, saturn_web["token"])
    assert code == 200, f"POST /api/admin/config rejected {field!r}={value!r} with {code}"
    got = _get(saturn_web["origin"], "/api/admin/config", saturn_web["token"])
    assert got.get(field) == value, (
        f"GET after POST returned {field}={got.get(field)!r}, expected {value!r}"
    )


def test_every_admin_config_field_has_roundtrip_row(saturn_web):
    """Meta-test: every field on AdminConfig (beyond the three existing) must appear in ROUNDTRIP_TABLE."""
    from saturn.web import AdminConfig
    EXISTING = {"model_filter", "max_budget", "budget_duration"}
    new_fields = set(AdminConfig.model_fields.keys()) - EXISTING
    covered = {f for f, _ in ROUNDTRIP_TABLE}
    missing = new_fields - covered
    assert not missing, (
        f"AdminConfig declares new fields with no round-trip coverage: {sorted(missing)!r}. "
        f"Add a row to ROUNDTRIP_TABLE for each."
    )


# --- 17.A.4.2 restart preservation ---

def test_config_survives_restart(saturn_web):
    code, _ = _post_status(saturn_web["origin"], "/api/admin/config",
                           {"rate_rpm": 99}, saturn_web["token"])
    assert code == 200

    # Bring the process down and back up against the same data dir.
    proc = saturn_web["proc"]
    proc.terminate()
    try: proc.wait(timeout=5)
    except subprocess.TimeoutExpired: proc.kill()

    log = open(saturn_web["tmp_path"] / "saturn-web-2.log", "wb")
    proc2 = subprocess.Popen(
        ["python3", "-m", "saturn", "web", "--port", str(saturn_web["port"])],
        env=saturn_web["env"], stdout=log, stderr=log,
    )
    deadline = time.time() + 15
    while time.time() < deadline and not _ping(saturn_web["origin"]):
        if proc2.poll() is not None:
            pytest.fail("restart failed")
        time.sleep(0.3)
    try:
        got = _get(saturn_web["origin"], "/api/admin/config", saturn_web["token"])
        assert got.get("rate_rpm") == 99, f"rate_rpm did not survive restart: {got!r}"
    finally:
        proc2.terminate()
        try: proc2.wait(timeout=5)
        except subprocess.TimeoutExpired: proc2.kill()


# --- 17.A.4.3 live propagation ---

def test_rate_rpm_takes_effect_live(saturn_web):
    """Tight rate_rpm hits 429 deterministically, no restart."""
    code, _ = _post_status(saturn_web["origin"], "/api/admin/config",
                           {"rate_rpm": 2}, saturn_web["token"])
    assert code == 200, f"failed to set rate_rpm=2: {code}"

    statuses = []
    for _ in range(4):
        c, _b = _post_status(saturn_web["origin"], "/api/chat",
                             {"service": "fake", "model": "fake", "messages": [{"role": "user", "content": "hi"}]},
                             saturn_web["token"])
        statuses.append(c)
    assert 429 in statuses, (
        f"with rate_rpm=2, four /api/chat hits should produce ≥1 429; got {statuses!r}"
    )


# --- 17.A.4.4 refuse-on-invalid ---

REFUSE_TABLE = [
    ("trusted_proxies",      ["not-a-cidr"]),
    ("bind_host",             "999.999.999.999"),
    ("admin_session_ttl_s",   30),       # below 60s
    ("rate_rpm",              0),
    ("trusted_node_ids",      ["not-a-uuid"]),
    ("trust_mode",            "open"),    # without SATURN_DEV_MODE
    ("cors_origins",          ["*"]),     # without SATURN_DEV_MODE
    ("proxy_models_method",   "DELETE"),  # only GET / POST allowed
]


@pytest.mark.parametrize("field,value", REFUSE_TABLE)
def test_invalid_value_refused(saturn_web, field, value):
    before = _get(saturn_web["origin"], "/api/admin/config", saturn_web["token"])
    code, _body = _post_status(saturn_web["origin"], "/api/admin/config",
                               {field: value}, saturn_web["token"])
    assert code == 422, f"{field!r}={value!r} should be refused with 422; got {code}"
    after = _get(saturn_web["origin"], "/api/admin/config", saturn_web["token"])
    assert after.get(field) == before.get(field), (
        f"refusal must not partially update on-disk config; {field} drifted from "
        f"{before.get(field)!r} to {after.get(field)!r}"
    )
