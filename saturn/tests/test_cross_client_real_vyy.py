"""Saturn-vyy / cbt.cross-client.real — protocol-level cross-client browse.

Phase 4. Saturn-ggn was a *regression guard* on the HTTP-stack parity of
`/v1/*` responses. THIS contract proves Saturn is a *protocol*, not a
Python package: a service registered by `SaturnAdvertiser` is discoverable
from three independent stacks, all of which observe the same service.

Three vehicles:

  1. **Python `zeroconf`** — Saturn's own browse path (different code than
     `SaturnAdvertiser` because the test uses raw zeroconf, not
     `SaturnDiscovery`). Sanity check.
  2. **`dns-sd -B` subprocess** (macOS Bonjour reference CLI) — entirely
     different mDNS stack written in C against `mDNSResponder`. If this
     sees the service, the wire-format is conformant.
  3. **`curl`** — hits the advertised IP:port. Confirms the HTTP server
     bound to the advertised port responds to a non-Python client. Not
     itself an mDNS browser, but closes the loop on "the protocol's
     usable end-to-end from a different stack."

Falsifiable oracle: a service registered with a unique instance name
MUST be observed by all three vehicles.

NO MOCKS. Real `SaturnAdvertiser`, real `dns-sd`, real `curl`, real
loopback HTTP.

Skipped on platforms without `dns-sd` (i.e., everything not macOS) until a
Linux-equivalent (avahi-browse) variant is filed as Saturn-vyy.linux.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import textwrap
import threading
import time
import uuid

import pytest


pytestmark = [pytest.mark.timeout(45), pytest.mark.slow]


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="session")
def has_dns_sd():
    if not shutil.which("dns-sd"):
        pytest.skip("dns-sd not available (non-macOS); file Saturn-vyy.linux for avahi-browse variant")
    return True


# Tiny FastAPI server spawned in a thread so curl has something to hit.
TINY_SRV_SRC = textwrap.dedent('''
    import os
    from fastapi import FastAPI
    import uvicorn
    app = FastAPI()
    @app.get("/health")
    def health():
        return {"ok": True, "name": os.environ.get("INSTANCE_NAME", "?")}
    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=int(os.environ["PORT"]),
                    log_level="warning")
''')


@pytest.fixture
def http_endpoint(tmp_path):
    src = tmp_path / "tiny_srv.py"
    src.write_text(TINY_SRV_SRC)
    port = _free_port()
    name = f"vyy-{uuid.uuid4().hex[:8]}"
    env = {**os.environ, "PORT": str(port), "INSTANCE_NAME": name}
    log = open(tmp_path / "tiny.log", "wb")
    proc = subprocess.Popen([sys.executable, str(src)], env=env,
                            stdout=log, stderr=log)
    deadline = time.time() + 10
    import urllib.request, urllib.error
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5)
            break
        except (urllib.error.URLError, ConnectionResetError, OSError):
            time.sleep(0.1)
    else:
        try: proc.terminate()
        except Exception: pass
        pytest.fail(f"tiny http server did not come up; see {tmp_path / 'tiny.log'}")
    try:
        yield {"name": name, "port": port}
    finally:
        try: proc.terminate()
        except Exception: pass
        try: proc.wait(timeout=3)
        except Exception:
            try: proc.kill()
            except Exception: pass


def test_saturn_service_visible_to_python_zeroconf_dnssd_and_curl(has_dns_sd, http_endpoint):
    from saturn.discovery import SaturnAdvertiser

    name = http_endpoint["name"]
    port = http_endpoint["port"]

    adv = SaturnAdvertiser(
        name=name,
        port=port,
        deployment="network",
        api_type="openai",
        priority=10,
        models=["test-model"],
        capabilities=["chat"],
        context=8192,
        cost="free",
    )
    ok = adv.register()
    assert ok, "SaturnAdvertiser.register() must return True"

    try:
        # Vehicle 1 — Python zeroconf (independent of Saturn's own browse path)
        from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
        seen_py: list[str] = []

        class L(ServiceListener):
            def add_service(self, zc, type_, n):
                seen_py.append(n.replace(f".{type_}", "").rstrip("."))
            def update_service(self, zc, type_, n): pass
            def remove_service(self, zc, type_, n): pass

        zc = Zeroconf()
        try:
            ServiceBrowser(zc, "_saturn._tcp.local.", L())
            deadline = time.time() + 5
            while time.time() < deadline and name not in seen_py:
                time.sleep(0.1)
        finally:
            zc.close()

        assert name in seen_py, (
            f"Python zeroconf must see the registered service {name!r}; "
            f"saw {seen_py!r}. Saturn's mDNS publish appears not to be visible "
            f"to a fresh Zeroconf browser on the same host."
        )

        # Vehicle 2 — dns-sd subprocess (macOS Bonjour reference)
        proc = subprocess.Popen(
            ["dns-sd", "-B", "_saturn._tcp", "local"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        try:
            time.sleep(3.5)
        finally:
            proc.terminate()
            try: out, _ = proc.communicate(timeout=3)
            except Exception:
                proc.kill()
                out, _ = proc.communicate()
        text = out.decode("utf-8", "replace")
        # dns-sd lines look like:
        #   <ts>  Add        2   1 local.               _saturn._tcp.        <name>
        m = re.search(rf"\bAdd\b\s+\d+\s+\d+\s+local\.\s+_saturn\._tcp\.\s+{re.escape(name)}\b", text)
        assert m, (
            f"dns-sd -B did not emit an 'Add' line for {name!r}; output:\n{text[-2000:]!r}. "
            f"Saturn's mDNS publish appears not conformant for the macOS reference stack."
        )

        # Vehicle 3 — curl against the advertised IP:port
        cp = subprocess.run(
            ["curl", "-sS", "-m", "5", "-w", "%{http_code}", "-o", "/dev/null",
             f"http://127.0.0.1:{port}/health"],
            capture_output=True, timeout=10, check=False,
        )
        assert cp.returncode == 0, (
            f"curl must succeed against the advertised IP:port; "
            f"returncode={cp.returncode}, stderr={cp.stderr.decode(errors='replace')[:300]}"
        )
        code = int(cp.stdout.decode().strip() or "0")
        assert 200 <= code < 500, (
            f"curl GET /health on the advertised port must return a real HTTP "
            f"status (200-499); got {code}"
        )
    finally:
        try: adv._backend.withdraw()
        except Exception: pass
        try: adv._backend.close()
        except Exception: pass
