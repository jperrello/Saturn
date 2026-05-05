"""Saturn-jfs / cbt.5.1.probe-dos — /api/discover rate limit.

Per FAILOVER_SECURITY.md §(C). `GET /api/discover` (saturn/web.py:661-683)
is **not rate-limited** — no `_check_rate(ip)` call. Each request runs
`discover(timeout=5.0)` + `isolation.probe(timeout=4.0)` ≈ 9 seconds of
blocking work plus one mDNS register/unregister cycle.

10 parallel requests = 90 process-seconds + 10 transient mDNS
announcements per cycle. Trivial DoS amplification.

Falsifiable oracle: with `SATURN_RATE_RPM=2`, sending 6 GET requests
to `/api/discover` rapidly MUST yield at least 3 HTTP 429 responses,
matching the existing per-IP rate limit applied to `/api/chat`,
`/api/proxy/chat`, and `/api/system/chat`.

NO MOCKS. Real saturn web subprocess with low rate-limit env.
"""

import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(120)


@pytest.fixture
def saturn_web_low_rpm(tmp_path):
    port = _free()
    token = "brutus-jfs-" + secrets.token_urlsafe(32)
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
        yield {"origin": origin}
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()


def _get(origin):
    req = urllib.request.Request(f"{origin}/api/discover")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_api_discover_burst_triggers_429(saturn_web_low_rpm):
    statuses = [_get(saturn_web_low_rpm["origin"]) for _ in range(6)]
    assert 429 in statuses, (
        f"6 rapid GET /api/discover with SATURN_RATE_RPM=2 MUST yield at least "
        f"one 429; got statuses={statuses!r}. /api/discover currently has no "
        f"_check_rate() gate (saturn/web.py:661-683); add it to match the rest "
        f"of the rate-limited /api/* surface and close the 9s-blocking-probe "
        f"DoS amplification (FAILOVER_SECURITY.md §C)."
    )
    assert statuses.count(429) >= 3, (
        f"with SATURN_RATE_RPM=2, at least 3 of 6 burst requests should be "
        f"rate-limited (bucket size N=2); got {statuses.count(429)} 429s in "
        f"{statuses!r}"
    )
