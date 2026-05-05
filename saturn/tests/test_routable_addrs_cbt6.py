"""Saturn-cbt.6 / §17.G.2 — routable_addrs() for multi-interface advertising.

Per PRE_SPECS_B3.md §17.G.2.2. New module `saturn/mdns/interfaces.py` MUST
expose:

  def routable_addrs() -> List[str]:
      '''All non-loopback IPv4 addresses on UP interfaces with default routes.'''

Implementation: `psutil.net_if_addrs()` filtered by `psutil.net_if_stats()
[iface].isup`, address family `AF_INET`. Excludes link-local (`169.254/16`)
and loopback (`127.0.0.0/8`).

This contract pins the pure-function surface. The userspace-backend
integration (`ServiceInfo(addresses=...)` carrying multiple addresses) is
filed as **cbt.6.userspace** sub-bead — separate red→green hop.

NO MOCKS. The function is exercised against the real OS interfaces of the
test machine.
"""

import socket

import pytest


def _iface_mod():
    try:
        return __import__("saturn.mdns.interfaces", fromlist=["routable_addrs"])
    except ImportError as e:
        pytest.fail(
            "module saturn/mdns/interfaces.py does not exist. "
            "Create it per PRE_SPECS_B3.md §17.G.2.2 with: "
            "def routable_addrs() -> list[str] returning all non-loopback, "
            "non-link-local IPv4 addresses on UP interfaces. "
            f"Raw import error: {e}"
        )


def _is_valid_ipv4(s):
    try:
        socket.inet_aton(s)
    except (OSError, TypeError):
        return False
    return s.count(".") == 3


def test_routable_addrs_returns_list_of_ipv4_strings():
    m = _iface_mod()
    result = m.routable_addrs()
    assert isinstance(result, list), f"routable_addrs() must return a list; got {type(result).__name__}"
    for addr in result:
        assert isinstance(addr, str), f"each addr must be str; got {addr!r}"
        assert _is_valid_ipv4(addr), f"each addr must be a valid IPv4 dotted-quad; got {addr!r}"


def test_routable_addrs_excludes_loopback_and_link_local():
    m = _iface_mod()
    result = m.routable_addrs()
    bad = [a for a in result if a.startswith("127.") or a.startswith("169.254.")]
    assert not bad, (
        f"routable_addrs() must exclude loopback (127.x) and link-local (169.254.x); "
        f"got disallowed entries: {bad!r}"
    )


def test_routable_addrs_finds_at_least_one_on_typical_host():
    m = _iface_mod()
    result = m.routable_addrs()
    assert len(result) >= 1, (
        f"on a typical dev machine with at least one UP non-loopback interface, "
        f"routable_addrs() must return at least one address; got {result!r}. "
        f"If this fires on a deliberately offline test host, gate with "
        f"`pytest.skip` rather than weakening the oracle."
    )
