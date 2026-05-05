"""Saturn-pcj / cbt.6.userspace — UserspaceBackend.advertise uses routable_addrs().

Per PRE_SPECS_B3.md §17.G.2.3. `saturn/mdns/userspace.py:121-125`'s
`advertise()` currently builds:

    host_ip = get_lan_ip()
    addr = [socket.inet_aton(host_ip)]

— a single-element address list. On a multi-NIC host, peers on the *other*
NIC's subnet won't see the service. The fix MUST source the address list
from `saturn.mdns.interfaces.routable_addrs()`.

Falsifiable oracle: when `routable_addrs()` reports two non-loopback IPv4
addresses, the registered `ServiceInfo.addresses` carries both packed
4-byte representations.

NO MOCKS of external services or libraries. The test injects two
addresses into Saturn's own `routable_addrs` helper via monkeypatch — this
is a test-boundary control, not a mock of an external dependency.
"""

import socket
import uuid

import pytest


pytestmark = [pytest.mark.timeout(15)]


def test_userspace_advertise_uses_routable_addrs_for_multi_addr():
    from saturn.mdns import interfaces as ifaces_mod
    from saturn.mdns import userspace as us_mod
    from saturn.mdns.backend import AdvertiseSpec

    fake_addrs = ["192.168.50.10", "192.168.60.10"]
    # Inject into both modules in case userspace imports the symbol directly.
    orig_iface = ifaces_mod.routable_addrs
    ifaces_mod.routable_addrs = lambda: list(fake_addrs)
    if hasattr(us_mod, "routable_addrs"):
        orig_us = us_mod.routable_addrs
        us_mod.routable_addrs = lambda: list(fake_addrs)
    else:
        orig_us = None

    backend = us_mod.UserspaceBackend()
    spec = AdvertiseSpec(
        name=f"pcj-{uuid.uuid4().hex[:6]}",
        port=9990,
        txt={"v": "1.0", "deployment": "network", "api_type": "openai",
             "priority": "10", "models": "x"},
    )
    try:
        backend.advertise(spec)
        info = backend._info
        assert info is not None, "advertise() must publish a ServiceInfo to _info"
        decoded = []
        for a in info.addresses or []:
            if isinstance(a, (bytes, bytearray)) and len(a) == 4:
                decoded.append(socket.inet_ntoa(a))
        for want in fake_addrs:
            assert want in decoded, (
                f"routable_addrs() reported {fake_addrs!r} but ServiceInfo.addresses "
                f"only carries {decoded!r}. UserspaceBackend.advertise must source "
                f"its address list from saturn.mdns.interfaces.routable_addrs() "
                f"(per §17.G.2.3), not the single-IP get_lan_ip() shortcut."
            )
    finally:
        try: backend.close()
        except Exception: pass
        ifaces_mod.routable_addrs = orig_iface
        if orig_us is not None:
            us_mod.routable_addrs = orig_us
