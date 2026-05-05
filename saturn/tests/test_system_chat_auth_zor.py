"""Saturn-zor / cbt.4.sec.token — /api/system/chat auth gate.

Phase 3 security hardening of the cbt.4 failover surface. Today
`saturn/web.py:1062-1063` exposes `POST /api/system/chat` with NO auth
gate — every other admin-scope endpoint in the same file uses
`Depends(require_admin)` (e.g., `/api/system/status` at line 1274). The
failover endpoint must enforce the same admin-token check.

Falsifiable oracle:

  - POST /api/system/chat with NO Authorization header → 401
  - POST /api/system/chat with WRONG bearer token → 401
  - POST /api/system/chat with CORRECT admin token → not-401 (any other
    status proves auth passed; here it'll be 502 because no backends are
    discovered in the test fixture)

NO MOCKS. Real Saturn web subprocess.
"""

import json
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(60)


@pytest.fixture
def saturn_web(tmp_path):
    port = _free()
    token = "brutus-zor-" + secrets.token_urlsafe(32)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "SATURN_ADMIN_TOKEN":    token,
        "SATURN_RUNNER_TOKEN":   "brutus-runner-" + secrets.token_urlsafe(32),
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
        yield {"origin": origin, "token": token}
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()


def _post_chat(origin, headers):
    body = {"messages": [{"role": "user", "content": "hi"}]}
    req = urllib.request.Request(
        f"{origin}/api/system/chat",
        data=json.dumps(body).encode(),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_no_auth_returns_401(saturn_web):
    status = _post_chat(saturn_web["origin"], headers={})
    assert status == 401, (
        f"POST /api/system/chat without Authorization MUST return 401; got {status}. "
        f"Add `_=Depends(require_admin)` to brutus_chat at saturn/web.py:1062-1063 "
        f"so the failover surface matches the rest of /api/system/* (status, tunnel/*)."
    )


def test_wrong_token_returns_401(saturn_web):
    status = _post_chat(saturn_web["origin"],
                        headers={"Authorization": "Bearer wrong-token-no-match"})
    assert status == 401, (
        f"POST /api/system/chat with wrong bearer token MUST return 401; got {status}."
    )


def test_correct_token_passes_auth(saturn_web):
    status = _post_chat(saturn_web["origin"],
                        headers={"Authorization": f"Bearer {saturn_web['token']}"})
    assert status != 401, (
        f"POST /api/system/chat with correct admin token MUST NOT return 401 "
        f"(no backends → 502 expected); got 401 instead, suggesting the auth gate "
        f"is rejecting the legitimate token."
    )


# --- folded P3 (geoff audit): BrutusChat.messages must have max_items cap ---

def _post_chat_body(origin, headers, body):
    req = urllib.request.Request(
        f"{origin}/api/system/chat",
        data=json.dumps(body).encode(),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_oversized_messages_list_returns_422(saturn_web):
    # 10001 messages — well past any reasonable conversation length; serves as
    # a spray vector for memory pressure and downstream prompt-budget abuse.
    body = {"messages": [{"role": "user", "content": "x"} for _ in range(10001)]}
    status = _post_chat_body(
        saturn_web["origin"],
        {"Authorization": f"Bearer {saturn_web['token']}"},
        body,
    )
    assert status == 422, (
        f"POST /api/system/chat with messages=[10001 items] MUST return 422 "
        f"(Pydantic validation failure) per geoff's audit P3 finding; got "
        f"{status}. Add `messages: List[dict] = Field(..., max_length=N)` "
        f"to BrutusChat at saturn/web.py:1036 with N around 200-500."
    )
