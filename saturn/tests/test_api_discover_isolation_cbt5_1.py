"""Saturn-5yh / cbt.5.1 — wire isolation.probe() into /api/discover.

Per PRE_SPECS_B3.md §17.G.1.3 and PARITY_REVIEW_MAY05.md §(c) Saturn-cbt.5.1.
The shipped `saturn/mdns/isolation.py` module is not consumed by the
runtime. `GET /api/discover` (saturn/web.py:614-633) currently returns a
bare list; it MUST return:

    {"services": [...], "isolation": {<IsolationProbe-shaped dict>}}

so the Web-UI Network Scan tab can distinguish "no peers exist" from
"network is hostile to multicast" per §17.G.1.4.

This contract pins the server-side response shape only. The Web-UI render
update at `Web-UI/app.js:946` is filed as **cbt.5.1.ui** (route to bombadil).

NO MOCKS. Real saturn web subprocess + real isolation probe.
"""

import json
import os
import secrets
import subprocess
import time
import urllib.request

import pytest

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(60)


@pytest.fixture
def saturn_web(tmp_path):
    port = _free()
    token = "brutus-5yh-" + secrets.token_urlsafe(16)
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


def test_api_discover_returns_services_and_isolation(saturn_web):
    req = urllib.request.Request(f"{saturn_web['origin']}/api/discover")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())

    assert isinstance(body, dict), (
        f"GET /api/discover must return a JSON object with `services` and "
        f"`isolation` keys per §17.G.1.3; got top-level type {type(body).__name__}: "
        f"{str(body)[:200]!r}"
    )
    assert "services" in body and isinstance(body["services"], list), (
        f"response must contain `services: list[...]` (the previous bare-list shape, "
        f"now nested); got keys {sorted(body.keys())!r}"
    )
    assert "isolation" in body and isinstance(body["isolation"], dict), (
        f"response must contain `isolation: dict` (IsolationProbe-shaped) per "
        f"§17.G.1.3 + PARITY_REVIEW cbt.5.1; got keys {sorted(body.keys())!r}"
    )
    iso = body["isolation"]
    expected = {"advertising", "self_seen", "peers_seen", "ifaces_with_link",
                "suspected_ap_isolation", "diagnosis"}
    missing = expected - set(iso.keys())
    assert not missing, (
        f"isolation dict must carry the IsolationProbe fields {expected!r}; "
        f"missing {sorted(missing)!r}; got {sorted(iso.keys())!r}"
    )
    assert isinstance(iso["diagnosis"], str), (
        f"isolation.diagnosis must be a string; got {type(iso['diagnosis']).__name__}"
    )
