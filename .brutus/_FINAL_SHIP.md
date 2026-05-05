# _FINAL_SHIP.md — MAY05 ship manifest

Branch: `autonomous/promo-push`. 30 brutus contracts, 30 green.

## Beads shipped (id · commit · one-line)

- Saturn-cbt.1 · `347bdc9` · saturn_meta receipt lifted to /api/proxy/chat + runner /v1/chat/completions
- Saturn-cbt.4 · `4f05fdb` · client-side failover (timeout + sticky + model affinity + routing.events receipt)
- Saturn-oqm (cbt.2.a) · regression-guard · long-message HTTP path streams promptly with intact saturn_meta
- Saturn-c4n · `5ac0a28` · MCP unreachable-server error is human-readable (no anyio TaskGroup leak)
- Saturn-ex3 · `83633d3` · MCP per-call asyncio.wait_for deadline (5min hang → <10s abort)
- Saturn-eic · `4961da8` · MCP oversized tool payloads hard-rejected (10 MiB no longer buffered)
- Saturn-o6a (cbt.3.a) · `75c58f9` · settle_time arg plumbed into SettleDetector
- Saturn-nu4 (cbt.3.b) · `2c9ef90` · userspace _resolve dispatched off the zeroconf listener thread
- Saturn-3to (cbt.3.c) · `8d2bbfd` · known_nodes.json fcntl.flock cross-process safety
- Saturn-6m1 (cbt.3.d) · `fa57189` · SaturnService.last_seen + discover(max_age=...) zombie filter
- Saturn-cbt.5 · `5c7410c` · AP-isolation probe (saturn/mdns/isolation.py)
- Saturn-cbt.6 · `f99354d` · routable_addrs() helper (saturn/mdns/interfaces.py)
- Saturn-cbt.7 · `d30e014` · ServiceRecord.addresses + SaturnService.{addresses, ipv6} dual-stack schema
- Saturn-cbt.8 · `173ad9e` · TXT advertise-time validator (saturn/mdns/txt.py)
- Saturn-76f · `3a2cc30` · connect_address(service) + SATURN_PREFER_V6 env
- Saturn-bfx · `6df7367` · advertiser TXT validate + prune + mtrunc + fail-loud
- Saturn-pcj · `78b0a64` · UserspaceBackend.advertise binds all routable_addrs
- Saturn-5yh · `b6b184f` · /api/discover returns {services, isolation}
- Saturn-1xh · `0ccab52` · userspace _resolve walks v4+v6 (inet_ntoa + inet_ntop)
- Saturn-9rv · `e7b6adf` · advertise-side dual-stack v4+v6 with routable_addrs(family=...)
- Saturn-7sg · `189a86d` · _add() merges addresses across events for same (node_id, name)
- Saturn-an5 · `c53760c` · SaturnDiscovery.sweep_stale(max_age) in-memory eviction
- Saturn-zor · `b6ab724` + `5eac74a` · /api/system/chat admin-token gate + BrutusChat.messages cap
- Saturn-b3o · `01808b9` · routing.events peer-name hashing + rate-limit regression guard
- Saturn-ggn · regression-guard · /v1/* HTTP-stack parity (urllib + httpx + curl)
- Saturn-vyy · regression-guard · protocol-level cross-client (zeroconf + dns-sd + curl)
- Saturn-x9c · `56ee730` · v6 filter ULA/6to4/Teredo/mixed-case fe80
- Saturn-zt2 · `0709ad6` · tunnel/VPN filter on isolation._link_ifaces
- Saturn-zd6 · `8c91f1f` · bounded _failover_state with TTL + LRU cap (P1)
- Saturn-xqw · `127f708` · api_base TXT SSRF gate (P1)
- Saturn-93w · `5930a72` · TOFU pin-race operator-asserted name→node_id allowlist (P1)
- Saturn-eon · `b19fb80` · sanitize ALL TXT values, not just models (P2)
- Saturn-jfs · `4330b4d` · /api/discover rate-limit gate (P2)
- Saturn-68j · `7222aba` · per-IP cap on _failover_state (P3)

## Totals

- Contracts authored: 30
- VERDICTs green: 30
- Hardener commits attested: 28 (+ 2 regression-guard contracts needing no fix)
- Geoff audit findings closed: 6 from FAILOVER_SECURITY.md (2× P1, 2× P2, 1× P3, + amends), 4 from PARITY_REVIEW_MAY05.md, 4 from DISCOVERY_AUDIT.md
- Beads routed to other lanes: 7 (UI / Go / Linux avahi / network harness)
- All P1+P2 security work: shipped

Brutus out.
