"""Saturn-x9c / cbt.7.advertise.v6filter — v6 filter gaps in interfaces.py.

Per geoff's security audit: `saturn/mdns/interfaces.py:24-28` filters out
only `::1`, `::`, and lowercase/uppercase `fe80:` link-local. It misses:

  - ULA (`fc00::/7` — `fc..` and `fd..`): RFC 4193 unique-local addresses
    are scope-bounded; advertising them on mDNS leaks topology and
    confuses external resolvers.
  - 6to4 (`2002::/16`): IPv4-tunnel-derived; reachability is unreliable
    and often blocked.
  - Teredo (`2001::/32`): UDP-tunneled IPv6; usually blocked, frequently
    behind NAT.
  - Mixed-case `fe80`: current filter handles only fully-lower and
    fully-upper. `Fe80:`, `fE80:` etc. slip through.

Falsifiable oracle: when `routable_addrs(family="v6")` is called with a
synthetic interface list containing one address from each disallowed
class plus one allowed global-ish address, ONLY the allowed address is
returned.

NO MOCKS of external services — `psutil` is monkeypatched as a
test-boundary control of the OS interface-listing API.
"""

import socket

import pytest


pytestmark = pytest.mark.timeout(10)


class _Stat:
    def __init__(self, isup): self.isup = isup


class _Addr:
    def __init__(self, family, address):
        self.family = family
        self.address = address
        self.netmask = None
        self.broadcast = None
        self.ptp = None


def test_v6_filter_excludes_ula_6to4_teredo_mixed_case_fe80(monkeypatch):
    import saturn.mdns.interfaces as ifaces
    import psutil

    fake_addrs_per_iface = {
        "eth0": [
            _Addr(socket.AF_INET6, "fc00::1"),         # ULA — must drop
            _Addr(socket.AF_INET6, "fd12:3456::1"),    # ULA — must drop
            _Addr(socket.AF_INET6, "2002:cb00:7102::1"),  # 6to4 — must drop
            _Addr(socket.AF_INET6, "2001::1234"),      # Teredo — must drop
            _Addr(socket.AF_INET6, "Fe80::abcd"),      # mixed-case fe80 — must drop
            _Addr(socket.AF_INET6, "2607:f8b0:4005:809::200e"),  # global — KEEP
        ]
    }
    fake_stats = {"eth0": _Stat(isup=True)}

    monkeypatch.setattr(psutil, "net_if_addrs", lambda: fake_addrs_per_iface)
    monkeypatch.setattr(psutil, "net_if_stats", lambda: fake_stats)

    out = ifaces.routable_addrs(family="v6")

    leaked = [a for a in out if (
        a.startswith("fc") or a.startswith("fd")
        or a.startswith("2002:")
        or a.startswith("2001:") and not a.startswith("2001:db8")  # Teredo
        or a.lower().startswith("fe80:")
    )]
    assert not leaked, (
        f"v6 filter must exclude ULA (fc/fd), 6to4 (2002::/16), Teredo "
        f"(2001::/32), and mixed-case fe80; leaked: {leaked!r}. "
        f"Tighten saturn/mdns/interfaces.py:24-28 with explicit prefix "
        f"checks (use `bare.lower().startswith(...)` for fe80) and the "
        f"three additional prefix families."
    )
    assert "2607:f8b0:4005:809::200e" in out, (
        f"v6 filter must keep legitimate global addresses; got {out!r}"
    )
