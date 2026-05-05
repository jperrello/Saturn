"""Saturn-cbt.3.a — settle_time plumbing in discover().

Per DISCOVERY_AUDIT.md (a). The `settle_time` argument on
`saturn.discovery.discover(timeout, settle_time)` (saturn/discovery.py:275) is
currently dead code: `SettleDetector()` is constructed without arguments, so
the hardcoded 0.5s timeout in `saturn/mdns/settle.py:5` always wins.

Falsifiable oracle: when one service is advertised on the network and
`discover(timeout=5.0, settle_time=3.0)` is called, the wall-clock time MUST
be at least 2.5s — proving the caller's `settle_time` is in effect. With the
current bug, total time is ~0.5s + brief detection latency (well under 2.5s).

NO MOCKS. Real Zeroconf publish + real SaturnDiscovery against the loopback
interface, mirroring the harness in saturn/tests/test_discovery.py.
"""

import socket
import time
import uuid

import pytest
from zeroconf import Zeroconf, ServiceInfo

from saturn.discovery import discover


pytestmark = [pytest.mark.timeout(20), pytest.mark.slow]


@pytest.fixture
def zc():
    z = Zeroconf(interfaces=["127.0.0.1"])
    yield z
    z.unregister_all_services()
    z.close()


def _register(zc, name, port=9991):
    stype = "_saturn._tcp.local."
    info = ServiceInfo(
        type_=stype,
        name=f"{name}.{stype}",
        port=port,
        addresses=[socket.inet_aton("127.0.0.1")],
        server=f"{name}.local.",
        properties={
            "version": "1.0",
            "deployment": "network",
            "api_type": "openai",
            "priority": "10",
            "models": "test-model",
            "capabilities": "chat",
            "context": "8192",
            "cost": "free",
        },
    )
    zc.register_service(info)
    return info


def test_settle_time_is_honoured_by_discover(zc):
    name = f"cbt3a-{uuid.uuid4().hex[:8]}"
    _register(zc, name)

    t0 = time.time()
    services = discover(timeout=5.0, settle_time=3.0)
    elapsed = time.time() - t0

    found = [s for s in services if s.name == name]
    assert found, (
        f"setup: advertised service '{name}' was not discovered at all; "
        f"got services={[s.name for s in services]!r}"
    )

    assert elapsed >= 2.5, (
        f"discover(timeout=5.0, settle_time=3.0) must respect the caller's "
        f"settle_time and wait at least ~3s after the last add; took {elapsed:.2f}s. "
        f"This proves settle_time is plumbed through to SettleDetector "
        f"(saturn/discovery.py:280 → saturn/mdns/settle.py:5)."
    )
    assert elapsed < 6.0, (
        f"discover() must still complete within `timeout`; took {elapsed:.2f}s "
        f"(timeout=5.0). Settle should not extend beyond the wall-clock cap."
    )
