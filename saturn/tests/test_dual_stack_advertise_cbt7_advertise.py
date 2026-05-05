"""Saturn-9rv / cbt.7.advertise (= cbt.7.2) — advertise-side AAAA records.

Per PRE_SPECS_B3.md §17.G.3.3 last paragraph + PARITY_REVIEW_MAY05.md §(c)
cbt.7.2. The advertiser MUST publish both AF_INET and AF_INET6 routable
addresses on `ServiceInfo.addresses` so dual-stack peers see the service
on whichever family they prefer.

Concrete contract:

  - `saturn.mdns.interfaces.routable_addrs()` MUST accept a `family`
    keyword (default `"both"`); other values: `"v4"`, `"v6"`. The default
    behavior of the no-arg call is unchanged from cbt.6 (returns v4 strings
    only) for back-compat with existing callers.
  - `UserspaceBackend.advertise()` (saturn/mdns/userspace.py:121-138) MUST
    pack both v4 (4-byte) and v6 (16-byte) entries into
    `ServiceInfo.addresses`. The selection helper is
    `routable_addrs(family="both")`.

This contract pins the advertise-side surface. Resolution-side AAAA
extraction is **Saturn-1xh / cbt.7.1** (separate contract, already RED).

NO MOCKS of external services — the test injects synthetic addresses into
Saturn's own `routable_addrs` as a test-boundary control.
"""

import socket
import uuid

import pytest


pytestmark = [pytest.mark.timeout(15)]


def test_routable_addrs_supports_family_kwarg():
    from saturn.mdns import interfaces as ifaces_mod
    sig_via_call = None
    try:
        sig_via_call = ifaces_mod.routable_addrs(family="both")
    except TypeError as e:
        pytest.fail(
            f"routable_addrs() must accept family= kwarg per §17.G.3.3 advertise-side. "
            f"Expected family in {{'v4','v6','both'}} (default 'v4' for back-compat). "
            f"Got TypeError: {e}"
        )
    assert isinstance(sig_via_call, list), (
        f"routable_addrs(family='both') must return list[str]; got {type(sig_via_call).__name__}"
    )


def test_userspace_advertise_packs_v4_and_v6_addresses():
    from saturn.mdns import interfaces as ifaces_mod
    from saturn.mdns import userspace as us_mod
    from saturn.mdns.backend import AdvertiseSpec

    fake_v4 = "192.168.50.10"
    fake_v6 = "fe80::abcd:1"

    def fake_routable(family="v4"):
        if family == "v4": return [fake_v4]
        if family == "v6": return [fake_v6]
        return [fake_v4, fake_v6]

    orig_iface = ifaces_mod.routable_addrs
    ifaces_mod.routable_addrs = fake_routable
    if hasattr(us_mod, "routable_addrs"):
        orig_us = us_mod.routable_addrs
        us_mod.routable_addrs = fake_routable
    else:
        orig_us = None

    backend = us_mod.UserspaceBackend()
    spec = AdvertiseSpec(
        name=f"9rv-{uuid.uuid4().hex[:6]}",
        port=9991,
        txt={"v": "1.0", "deployment": "network", "api_type": "openai",
             "priority": "10"},
    )
    try:
        backend.advertise(spec)
        info = backend._info
        assert info is not None, "advertise() must publish a ServiceInfo to _info"
        v4_decoded = [socket.inet_ntoa(a) for a in (info.addresses or []) if isinstance(a, (bytes, bytearray)) and len(a) == 4]
        v6_decoded = [socket.inet_ntop(socket.AF_INET6, a) for a in (info.addresses or []) if isinstance(a, (bytes, bytearray)) and len(a) == 16]
        assert fake_v4 in v4_decoded, (
            f"advertise must include the v4 routable addr; v4={v4_decoded!r}, v6={v6_decoded!r}"
        )
        assert any(a == fake_v6 for a in v6_decoded), (
            f"advertise must include the v6 routable addr (4-byte AF_INET + 16-byte AF_INET6 "
            f"both packed into ServiceInfo.addresses per §17.G.3.3); "
            f"v4={v4_decoded!r}, v6={v6_decoded!r}"
        )
    finally:
        try: backend.close()
        except Exception: pass
        ifaces_mod.routable_addrs = orig_iface
        if orig_us is not None:
            us_mod.routable_addrs = orig_us
