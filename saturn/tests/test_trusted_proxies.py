"""Saturn-qj5.16.3 — formal trusted_proxies allowlist + correct XFF parse.

Per SECURITY_AUDIT.md §8 + CONFIG_FIELDS §A.3.

Today (post qj5.16.10): hardener pre-emptively stripped untrusted XFF from the
usage attribution path (commit 3345dbb). The systemic fix — admin-configurable
`trusted_proxies` allowlist + rightmost-of-trusted-tail XFF parse — is
uncontracted. This file contracts it.

Falsifier (per user brief):
  - empty trusted_proxies   → XFF is ignored entirely (peer = request.client.host)
  - populated + last-hop matches allowlist → identity is the RIGHTMOST XFF entry
  - spoofed XFF from peer not in allowlist → XFF ignored
  - invalid CIDR in trusted_proxies → logs warning, skips, DOES NOT crash boot

Verification surface: /api/usage attribution. POST /api/usage/report tokens
under various peer/XFF combinations; admin GET /api/usage?user_id=<X> reads
back which IP was attributed. (qj5.16.10 already gated GET /api/usage behind
admin token; we use that.)

No mocks. Real Saturn web subprocess.
"""

import json
import os
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(120)


def _spawn_saturn(tmp_path, admin_cfg=None):
    """Spawn `python3 -m saturn web` with admin auth + optional admin_config.json. Returns (proc, origin, token)."""
    port = _free()
    token = "brutus-qj5.16.3-" + secrets.token_urlsafe(16)
    runner_tok = "brutus-runner-" + secrets.token_urlsafe(16)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    if admin_cfg is not None:
        (data_dir / "admin_config.json").write_text(json.dumps(admin_cfg))
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "SATURN_ADMIN_TOKEN":    token,
        "SATURN_RUNNER_TOKEN":   runner_tok,
        "SATURN_ADMIN_PASSWORD": MIN_PASSWORD,
        "SATURN_DATA_DIR":       str(data_dir),
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
            pytest.fail(f"saturn web exited; tail of log:\n{(tmp_path / 'saturn-web.log').read_text()[-1500:]}")
        time.sleep(0.3)
    if not _ping(origin):
        proc.terminate()
        pytest.fail("saturn web never came up")
    return proc, origin, token


def _stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()


def _admin(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _post(origin, path, body, headers):
    req = urllib.request.Request(
        f"{origin}{path}", data=json.dumps(body).encode(),
        headers=headers, method="POST",
    )
    try:
        return urllib.request.urlopen(req, timeout=10).getcode()
    except urllib.error.HTTPError as e:
        return e.code


def _get_usage(origin, admin_token, user_id):
    req = urllib.request.Request(
        f"{origin}/api/usage?user_id={user_id}",
        headers=_admin(admin_token), method="GET",
    )
    try:
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": (e.read() or b"").decode("utf-8", "replace")}


# --- 1. Empty trusted_proxies ⇒ XFF ignored ---

def test_empty_trusted_proxies_ignores_xff(tmp_path):
    proc, origin, admin = _spawn_saturn(tmp_path, admin_cfg={"trusted_proxies": []})
    try:
        # Spoof XFF claiming to be 9.9.9.9; socket peer is 127.0.0.1.
        spoof_headers = {"X-Forwarded-For": "9.9.9.9", "Content-Type": "application/json"}
        _post(origin, "/api/usage/report", {"tokens_in": 11, "tokens_out": 22}, spoof_headers)

        # Admin lookup: 9.9.9.9 should NOT have been attributed.
        spoofed = _get_usage(origin, admin, "9.9.9.9")
        assert spoofed.get("tokens_in", 0) == 0, (
            f"empty trusted_proxies must ignore XFF; 9.9.9.9 wrongly attributed: {spoofed!r}"
        )

        # The real socket peer (127.0.0.1) carries the tokens.
        peer = _get_usage(origin, admin, "127.0.0.1")
        assert peer.get("tokens_in", 0) >= 11 and peer.get("tokens_out", 0) >= 22, (
            f"with empty trusted_proxies, peer 127.0.0.1 must own the usage row; got {peer!r}"
        )
    finally:
        _stop(proc)


# --- 2. Trusted peer + XFF ⇒ rightmost entry wins ---

def test_trusted_peer_uses_rightmost_xff(tmp_path):
    proc, origin, admin = _spawn_saturn(tmp_path,
        admin_cfg={"trusted_proxies": ["127.0.0.1"]})
    try:
        # XFF chain: leftmost is the original (untrusted) client header,
        # rightmost is what the trusted proxy added (the real peer it saw).
        headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8", "Content-Type": "application/json"}
        _post(origin, "/api/usage/report", {"tokens_in": 33, "tokens_out": 44}, headers)

        # rightmost = 5.6.7.8 — that's the identity Saturn must trust.
        right = _get_usage(origin, admin, "5.6.7.8")
        assert right.get("tokens_in", 0) >= 33, (
            f"trusted_proxies=[127.0.0.1] + XFF '1.2.3.4, 5.6.7.8' must attribute to 5.6.7.8 "
            f"(rightmost — added by the trusted proxy); got {right!r}"
        )

        # Leftmost (attacker-controlled history) MUST NOT be the identity.
        left = _get_usage(origin, admin, "1.2.3.4")
        assert left.get("tokens_in", 0) == 0, (
            f"leftmost XFF entry 1.2.3.4 (attacker-controlled history) must not be trusted "
            f"as identity; got {left!r}"
        )

        # Peer 127.0.0.1 must NOT carry the tokens — it's the trusted proxy, not the client.
        peer = _get_usage(origin, admin, "127.0.0.1")
        assert peer.get("tokens_in", 0) == 0, (
            f"trusted proxy peer 127.0.0.1 must hand off identity to rightmost XFF; got {peer!r}"
        )
    finally:
        _stop(proc)


# --- 3. Untrusted peer + XFF ⇒ XFF ignored ---

def test_untrusted_peer_ignores_xff(tmp_path):
    """trusted_proxies points at a network the peer is NOT in (10.0.0.0/8); XFF must not be honoured."""
    proc, origin, admin = _spawn_saturn(tmp_path,
        admin_cfg={"trusted_proxies": ["10.0.0.0/8"]})
    try:
        headers = {"X-Forwarded-For": "9.9.9.9", "Content-Type": "application/json"}
        _post(origin, "/api/usage/report", {"tokens_in": 7, "tokens_out": 8}, headers)

        spoofed = _get_usage(origin, admin, "9.9.9.9")
        assert spoofed.get("tokens_in", 0) == 0, (
            f"peer 127.0.0.1 NOT in trusted_proxies=[10.0.0.0/8]; XFF must be ignored. "
            f"9.9.9.9 wrongly attributed: {spoofed!r}"
        )
        peer = _get_usage(origin, admin, "127.0.0.1")
        assert peer.get("tokens_in", 0) >= 7
    finally:
        _stop(proc)


# --- 4. Invalid CIDR ⇒ skip-and-warn, don't crash ---

def test_invalid_cidr_does_not_crash_boot(tmp_path):
    """A bad CIDR alongside a good one logs a warning and is skipped; saturn web still comes up."""
    proc, origin, admin = _spawn_saturn(tmp_path,
        admin_cfg={"trusted_proxies": ["not-a-cidr", "127.0.0.1"]})
    try:
        # Boot succeeded if we reached here. Verify the GOOD CIDR still does its job:
        # spoofed XFF from the trusted peer is honoured (rightmost wins).
        headers = {"X-Forwarded-For": "10.0.0.42", "Content-Type": "application/json"}
        _post(origin, "/api/usage/report", {"tokens_in": 5, "tokens_out": 5}, headers)
        good = _get_usage(origin, admin, "10.0.0.42")
        assert good.get("tokens_in", 0) >= 5, (
            f"the surviving good CIDR (127.0.0.1) must still trust the proxy; got {good!r}"
        )
    finally:
        _stop(proc)


# --- 5. Live propagation: changing trusted_proxies via /api/admin/config takes effect ---

def test_trusted_proxies_takes_effect_live(tmp_path):
    """Per CONFIG_FIELDS §A.3: trusted_proxies must lift/reload without a process restart."""
    proc, origin, admin = _spawn_saturn(tmp_path, admin_cfg={"trusted_proxies": []})
    try:
        # Step 1: empty allowlist — XFF ignored.
        headers = {"X-Forwarded-For": "5.5.5.5", "Content-Type": "application/json"}
        _post(origin, "/api/usage/report", {"tokens_in": 1, "tokens_out": 1}, headers)
        before = _get_usage(origin, admin, "5.5.5.5")
        assert before.get("tokens_in", 0) == 0

        # Step 2: admin POST trusted_proxies=["127.0.0.1"] — no restart.
        _post(origin, "/api/admin/config",
              {"trusted_proxies": ["127.0.0.1"]}, _admin(admin))

        # Step 3: now XFF rightmost (5.5.5.5) should be honoured.
        _post(origin, "/api/usage/report", {"tokens_in": 9, "tokens_out": 9}, headers)
        after = _get_usage(origin, admin, "5.5.5.5")
        assert after.get("tokens_in", 0) >= 9, (
            f"trusted_proxies update did not take effect live; 5.5.5.5 still missing tokens: {after!r}"
        )
    finally:
        _stop(proc)
