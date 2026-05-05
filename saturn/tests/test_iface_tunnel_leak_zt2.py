"""Saturn-zt2 / cbt.5.1.tunnel-leak — isolation.ifaces_with_link leaks tunnels/VPN.

Geoff's security audit: `saturn/mdns/isolation._link_ifaces()` enumerates
every UP interface (except loopback) and returns the names verbatim. The
list is then surfaced via `/api/discover` → `isolation.ifaces_with_link`
to anyone who can hit the endpoint (no auth gate today on /api/discover).
This leaks the host's VPN / tunnel / container topology:

  - tun0, tun1, … (OpenVPN, generic TUN)
  - utun0, utun1, … (macOS userspace tunnels: Tailscale, IKEv2, etc.)
  - wg0, wg1 (WireGuard)
  - tap0, tap1 (TAP devices)
  - docker0, docker_gwbridge (Docker)
  - veth*  (virtual ethernet pairs)
  - ipsec*, gif*, stf* (BSD tunnels)

Falsifiable oracle: with a synthetic interface set containing one
"normal" interface (`en0`) plus one of each tunnel class, `_link_ifaces()`
MUST return ONLY `en0`.

NO MOCKS of external services. `psutil` monkeypatched as a test-boundary
control of OS interface enumeration.
"""

import pytest


pytestmark = pytest.mark.timeout(10)


class _Stat:
    def __init__(self, isup): self.isup = isup


def test_link_ifaces_excludes_tunnels_and_vpn(monkeypatch):
    import psutil
    import saturn.mdns.isolation as iso

    fake_stats = {
        "lo0":              _Stat(isup=True),  # loopback (already excluded)
        "en0":              _Stat(isup=True),  # KEEP — real wifi/ethernet
        "tun0":             _Stat(isup=True),  # OpenVPN
        "utun3":            _Stat(isup=True),  # macOS Tailscale / IKEv2
        "wg0":              _Stat(isup=True),  # WireGuard
        "tap0":             _Stat(isup=True),  # TAP device
        "docker0":          _Stat(isup=True),  # Docker
        "docker_gwbridge":  _Stat(isup=True),  # Docker
        "veth1234abcd":     _Stat(isup=True),  # veth pair
        "ipsec0":           _Stat(isup=True),  # IPSec
        "gif0":             _Stat(isup=True),  # BSD generic tunnel
    }
    monkeypatch.setattr(psutil, "net_if_stats", lambda: fake_stats)

    out = iso._link_ifaces()

    leaked = [name for name in out if name in (
        "tun0", "utun3", "wg0", "tap0", "docker0", "docker_gwbridge",
        "veth1234abcd", "ipsec0", "gif0",
    )]
    assert not leaked, (
        f"_link_ifaces() must filter tunnel/VPN/container interfaces; "
        f"leaked: {leaked!r}. Per geoff's audit, the public "
        f"/api/discover.isolation.ifaces_with_link field exposes this list "
        f"to anyone who can hit /api/discover. Tighten the filter at "
        f"saturn/mdns/isolation.py:23-33 to drop names matching "
        f"{{tun*, utun*, wg*, tap*, docker*, veth*, ipsec*, gif*, stf*}}."
    )
    assert "en0" in out, (
        f"_link_ifaces() must keep legitimate physical interfaces; got {out!r}"
    )
