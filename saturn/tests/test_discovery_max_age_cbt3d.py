"""Saturn-cbt.3.d — last_seen + max_age on discover().

Per DISCOVERY_AUDIT.md (d). `SaturnService` (saturn/discovery.py:75-95) has no
`last_seen` field today, and `discover()` (line 275) takes only
`(timeout, settle_time)`. There is no Saturn-level way for callers to filter
zombie entries — when an advertiser dies hard (no goodbye), the underlying
mDNS library's TTL eventually evicts but Saturn cannot bound that window.

Falsifiable oracle:

  1. Each `SaturnService` returned by `discover()` carries a numeric
     `last_seen` field that is a unix timestamp within the last 30s of when
     `discover()` returned. Proves the timestamp is recorded by Saturn (not
     just inferred from the underlying library).

  2. `discover()` accepts a `max_age: float` kwarg. When set to `0.0` against
     a freshly-discovered service, the result MUST exclude that service (no
     entry is younger than 0s). When set to a generous value (e.g. 600.0),
     the service MUST be included. Proves the filter is wired.

NO MOCKS. Real Zeroconf publish on loopback.

The full liveness-probe sweep (active /v1/health pings to evict zombies on a
running `SaturnDiscovery`) is intentionally out of scope here — it cross-cuts
cbt.4 and warrants its own contract (cbt.3.d.sweep).
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


def _register(zc, name, port=9992):
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


def test_saturnservice_carries_last_seen_timestamp(zc):
    name = f"cbt3d-{uuid.uuid4().hex[:8]}"
    _register(zc, name)

    services = discover(timeout=4.0, settle_time=1.0)
    returned_at = time.time()

    found = [s for s in services if s.name == name]
    assert found, (
        f"setup: advertised service '{name}' was not discovered; "
        f"got {[s.name for s in services]!r}"
    )
    s = found[0]

    assert hasattr(s, "last_seen"), (
        f"SaturnService must carry a `last_seen` field (unix seconds float). "
        f"Currently no such attribute. Add it to the dataclass at "
        f"saturn/discovery.py:75-95 and populate it on each add/update event."
    )
    ls = getattr(s, "last_seen")
    assert isinstance(ls, (int, float)) and ls > 0, (
        f"last_seen must be a positive unix-seconds number; got {ls!r}"
    )
    assert returned_at - 30 <= ls <= returned_at + 1, (
        f"last_seen must be within ~30s of `discover()` return; "
        f"discover returned at {returned_at}, last_seen={ls} (delta={returned_at-ls:.1f}s)"
    )


def test_discover_max_age_kwarg_filters_old_entries(zc):
    name = f"cbt3d-{uuid.uuid4().hex[:8]}"
    _register(zc, name)

    # max_age = 0.0 → no entry can be 0 seconds old → result excludes everything
    excluded = discover(timeout=4.0, settle_time=1.0, max_age=0.0)
    assert all(s.name != name for s in excluded), (
        f"discover(max_age=0.0) must exclude all entries (none can be ≤0s old); "
        f"got names={[s.name for s in excluded]!r}. "
        f"Implement max_age filter on the result list of discover() based on last_seen."
    )

    included = discover(timeout=4.0, settle_time=1.0, max_age=600.0)
    assert any(s.name == name for s in included), (
        f"discover(max_age=600.0) must include the freshly-advertised service; "
        f"got names={[s.name for s in included]!r}"
    )
