"""Saturn-1xh / cbt.7.resolve (= cbt.7.1) — populate ServiceRecord.addresses
across backends.

Per PRE_SPECS_B3.md §17.G.3.3 and PARITY_REVIEW_MAY05.md §(c) cbt.7.1.
`saturn/mdns/userspace.py:28-47`'s `_resolve()` currently extracts only
`info.addresses[0]` via the IPv4-only `socket.inet_ntoa`. Per spec, the
returned `ServiceRecord.addresses` MUST carry every advertised address —
both 4-byte AF_INET and 16-byte AF_INET6 entries — converted to textual
form (`inet_ntoa` / `inet_ntop` respectively).

This contract pins the **userspace** backend's resolve plumbing only.
Bonjour and Avahi require their own per-backend wire-ins (file as
**cbt.7.resolve.bonjour** / **cbt.7.resolve.avahi** when those platform
paths are active).

NO MOCKS. Real Zeroconf register + real userspace `_resolve()`.
"""

import socket
import uuid

import pytest
from zeroconf import Zeroconf, ServiceInfo


pytestmark = [pytest.mark.timeout(15), pytest.mark.slow]


SERVICE_TYPE = "_saturn._tcp.local."


@pytest.fixture
def zc():
    z = Zeroconf(interfaces=["127.0.0.1"])
    yield z
    z.unregister_all_services()
    z.close()


def test_userspace_resolve_returns_both_v4_and_v6_addresses(zc):
    from saturn.mdns.userspace import _resolve
    name = f"cbt7r-{uuid.uuid4().hex[:8]}"
    v4_bytes = socket.inet_aton("127.0.0.1")
    v6_bytes = socket.inet_pton(socket.AF_INET6, "::1")
    info = ServiceInfo(
        type_=SERVICE_TYPE,
        name=f"{name}.{SERVICE_TYPE}",
        port=9999,
        addresses=[v4_bytes, v6_bytes],
        server=f"{name}.local.",
        properties={"version": "1.0"},
    )
    zc.register_service(info)

    rec = _resolve(zc, SERVICE_TYPE, f"{name}.{SERVICE_TYPE}")
    assert rec is not None, "resolve must succeed against locally-registered service"
    assert hasattr(rec, "addresses"), (
        "ServiceRecord must have addresses field (post-cbt.7 schema)"
    )
    assert "127.0.0.1" in rec.addresses, (
        f"v4 address must be present in textual form via inet_ntoa; "
        f"got addresses={rec.addresses!r}"
    )
    has_v6 = any((":" in a) and a in ("::1", "0:0:0:0:0:0:0:1") for a in rec.addresses)
    assert has_v6, (
        f"v6 address must be present in textual form via inet_ntop(AF_INET6, ...); "
        f"got addresses={rec.addresses!r}. Per §17.G.3.3 userspace _resolve must "
        f"walk info.addresses and dispatch on len(addr): 4 → inet_ntoa, "
        f"16 → inet_ntop(AF_INET6)."
    )
