"""Saturn-76f / cbt.7.prefer — IPv6 preference policy for connect-target.

Per PRE_SPECS_B3.md §17.G.3.5. Add a helper that, given a `SaturnService`
with both v4 and v6 addresses, returns the address the client should connect
to. Behavior:

  - SATURN_PREFER_V6 unset / "0" / "false" → return first non-v6 address
    (i.e., IPv4); back-compat default.
  - SATURN_PREFER_V6=1 / "true" → return first IPv6 address from
    `service.addresses`; fall back to IPv4 only if no v6 is present.

The exact symbol name is `saturn.discovery.connect_address(service) -> str`.
This contract pins the helper's surface and behavior — URL construction
(bracketing v6 hosts) is the caller's responsibility.

NO MOCKS. Pure-function; env via monkeypatch.
"""

import pytest


def _make_service(addresses, host="ignored.local"):
    from saturn.discovery import SaturnService
    return SaturnService(name="x", host=host, port=8080, addresses=addresses,
                         ipv6=(next((a for a in addresses if ":" in a), None)))


def test_default_returns_ipv4_when_both_present(monkeypatch):
    monkeypatch.delenv("SATURN_PREFER_V6", raising=False)
    try:
        from saturn.discovery import connect_address
    except ImportError:
        pytest.fail(
            "saturn.discovery must expose connect_address(service) -> str. "
            "Per §17.G.3.5: respects SATURN_PREFER_V6 env var; default returns "
            "first IPv4."
        )
    s = _make_service(["192.168.1.10", "fe80::1"])
    addr = connect_address(s)
    assert addr == "192.168.1.10", (
        f"default (no SATURN_PREFER_V6) must return the IPv4 address; got {addr!r}"
    )


def test_prefer_v6_returns_ipv6_when_available(monkeypatch):
    monkeypatch.setenv("SATURN_PREFER_V6", "1")
    from saturn.discovery import connect_address
    s = _make_service(["192.168.1.10", "fe80::1"])
    addr = connect_address(s)
    assert addr == "fe80::1", (
        f"with SATURN_PREFER_V6=1 and v6 available, must return the IPv6; got {addr!r}"
    )


def test_prefer_v6_falls_back_to_v4_when_no_v6(monkeypatch):
    monkeypatch.setenv("SATURN_PREFER_V6", "1")
    from saturn.discovery import connect_address
    s = _make_service(["192.168.1.10"])
    addr = connect_address(s)
    assert addr == "192.168.1.10", (
        f"with SATURN_PREFER_V6=1 but no v6 in addresses, must fall back to v4; "
        f"got {addr!r}"
    )
