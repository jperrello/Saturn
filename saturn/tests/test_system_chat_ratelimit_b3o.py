"""Saturn-b3o / cbt.4.sec.ratelimit — /api/system/chat rate limiting.

Phase 3 security hardening of the cbt.4 failover surface. The existing
`_check_rate` infrastructure (saturn/web.py:293) is already wired into
`brutus_chat` (line 1065), but until pinned, a future refactor could
silently drop the gate. This contract pins the rate-limit invariant as
load-bearing.

Falsifiable oracle: with `SATURN_RATE_RPM=2`, sending 6 POST requests to
`/api/system/chat` from the same client in rapid succession MUST yield at
least one HTTP **429** response (with a `Retry-After` header), and the
first 1-2 requests MUST not be 429 (proves the limit is N, not 0).

NO MOCKS. Real Saturn web subprocess with low rate-limit env.
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
def saturn_web_low_rpm(tmp_path):
    port = _free()
    token = "brutus-b3o-" + secrets.token_urlsafe(32)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "SATURN_ADMIN_TOKEN":    token,
        "SATURN_RUNNER_TOKEN":   "brutus-runner-" + secrets.token_urlsafe(32),
        "SATURN_ADMIN_PASSWORD": MIN_PASSWORD,
        "SATURN_DATA_DIR":       str(tmp_path / "data"),
        "SATURN_SERVICES_DIR":   str(tmp_path / "services"),
        "SATURN_BIND_HOST":      "127.0.0.1",
        "SATURN_RATE_RPM":       "2",
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


def _post_chat(origin, token):
    body = {"messages": [{"role": "user", "content": "hi"}]}
    req = urllib.request.Request(
        f"{origin}/api/system/chat",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {})


def test_burst_triggers_429(saturn_web_low_rpm):
    statuses = []
    headers_at_429 = None
    for _ in range(6):
        s, h = _post_chat(saturn_web_low_rpm["origin"], saturn_web_low_rpm["token"])
        statuses.append(s)
        if s == 429 and headers_at_429 is None:
            headers_at_429 = h

    assert 429 in statuses, (
        f"6 rapid POST /api/system/chat with SATURN_RATE_RPM=2 MUST yield at "
        f"least one 429; got statuses={statuses!r}. Per-IP rate limit at "
        f"saturn/web.py:1065 (_check_rate) must remain wired."
    )
    assert statuses.count(429) >= 3, (
        f"with SATURN_RATE_RPM=2, at least 3 of 6 burst requests should be "
        f"rate-limited (the bucket holds ~2 then refills slowly); got "
        f"{statuses.count(429)} 429s in {statuses!r}"
    )
    assert headers_at_429 and "retry-after" in {k.lower() for k in headers_at_429}, (
        f"429 response MUST include a Retry-After header; got headers "
        f"{sorted(headers_at_429.keys())!r}"
    )
    # First 1-2 requests must not be 429 (limit is N=2, not 0).
    assert statuses[0] != 429, (
        f"first request must not be rate-limited at SATURN_RATE_RPM=2; got "
        f"statuses[0]={statuses[0]}"
    )
