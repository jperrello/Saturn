"""Saturn-68j / cbt.4.sec.zd6.per_ip — per-IP cap on _failover_state.

P3 follow-up to Saturn-zd6 (which closed the global-cap + TTL halves of
the DoS finding). The remaining gap: a single attacker IP can still
consume up to all `MAX_STICKY=10000` slots by spraying unique
conversation IDs, evicting legitimate users' entries via the FIFO eviction.

Geoff scoped fix: per-IP cap (suggest 100 active sticky entries per
client IP; oldest-from-that-IP evicted on overflow).

Required surface:

  - `saturn.web.MAX_STICKY_PER_IP: int` — module constant, default
    ≥ 10 (suggest 100 in production; the test uses a lower value via
    monkeypatch).
  - `saturn.web._set_sticky(convo_id, peer, ip)` — the only sanctioned
    write path. The existing call site at `saturn/web.py:1266` MUST be
    updated to call this helper with the request IP.

Falsifiable oracles:

  1. **Per-IP cap holds.** With `MAX_STICKY_PER_IP=10`, after 15
     `_set_sticky` calls from a single IP, that IP's footprint MUST be
     ≤ 10 (i.e., at most 10 of those 15 keys are still present).
  2. **Cross-IP isolation.** Spamming from IP1 MUST NOT evict entries
     attributed to IP2. With cap=10 and IP2 having only 5 entries, IP1
     pumping 11 entries leaves IP2's 5 untouched.

NO MOCKS. Pure in-process exercise of `_failover_state` + the new
`_set_sticky` helper.
"""

import pytest


pytestmark = pytest.mark.timeout(15)


def _W():
    """Import saturn.web fresh so test ordering doesn't matter."""
    import saturn.web as W
    return W


def test_per_ip_cap_enforces(monkeypatch):
    W = _W()
    assert hasattr(W, "MAX_STICKY_PER_IP"), (
        "saturn.web must expose `MAX_STICKY_PER_IP: int` as a module "
        "constant per geoff's zd6 follow-up. Today the constant is "
        "missing; one IP can still spray unique convo_ids up to MAX_STICKY."
    )
    assert hasattr(W, "_set_sticky"), (
        "saturn.web must expose `_set_sticky(convo_id, peer, ip)` as the "
        "sanctioned write path so per-IP attribution can be tracked. The "
        "current call site (saturn/web.py:1266) does `_failover_state[k] = v` "
        "without IP context."
    )

    monkeypatch.setattr(W, "MAX_STICKY_PER_IP", 10)
    W._failover_state.clear()

    ip = "1.2.3.4"
    for i in range(15):
        W._set_sticky(f"ip1-c-{i:02d}", "peer-a", ip)

    present = sum(1 for i in range(15) if f"ip1-c-{i:02d}" in W._failover_state)
    assert present <= 10, (
        f"per-IP cap violated: 15 sprays from a single IP at "
        f"MAX_STICKY_PER_IP=10 left {present} of 15 keys attributed to that "
        f"IP. Implement FIFO eviction per IP so an attacker can't pin more "
        f"than the cap regardless of how fast they spray."
    )


def test_per_ip_cap_isolates_ips(monkeypatch):
    W = _W()
    if not hasattr(W, "MAX_STICKY_PER_IP") or not hasattr(W, "_set_sticky"):
        pytest.skip("requires MAX_STICKY_PER_IP + _set_sticky (gated by previous test)")

    monkeypatch.setattr(W, "MAX_STICKY_PER_IP", 10)
    W._failover_state.clear()

    # Victim IP2 has 5 legit entries (well under cap)
    for i in range(5):
        W._set_sticky(f"ip2-c-{i:02d}", "peer-b", "9.8.7.6")

    # Attacker IP1 sprays 11 entries (over its cap)
    for i in range(11):
        W._set_sticky(f"ip1-c-{i:02d}", "peer-a", "1.2.3.4")

    ip2_survivors = sum(1 for i in range(5) if f"ip2-c-{i:02d}" in W._failover_state)
    ip1_survivors = sum(1 for i in range(11) if f"ip1-c-{i:02d}" in W._failover_state)

    assert ip2_survivors == 5, (
        f"cross-IP isolation violated: IP2's legitimate 5 entries should "
        f"survive a spray from IP1, but only {ip2_survivors} remain. "
        f"Per-IP eviction must NOT touch other IPs' entries."
    )
    assert ip1_survivors <= 10, (
        f"IP1 retained {ip1_survivors} of 11 entries at MAX_STICKY_PER_IP=10; "
        f"per-IP cap not enforced."
    )
