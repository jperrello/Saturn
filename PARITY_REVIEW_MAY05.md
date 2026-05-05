# PARITY_REVIEW_MAY05.md — shipped mDNS surface vs §17.G pre-specs

Branch: `autonomous/promo-push` · Author: geoff · Date: 2026-05-05 · Pass: rough

Reviewing `saturn/mdns/{txt,isolation,interfaces}.py` + `ServiceRecord` schema additions against `PRE_SPECS_B3.md §17.G.{1,2,3,4}` and `DISCOVERY_AUDIT.md`.

## Headline

**Three modules shipped clean as standalone surfaces with passing tests, but none are wired into the runtime call chain.** Tests cover the public API contract (per `saturn/tests/test_{txt_validate,routable_addrs,isolation}_*.py`), but the integration points specified in §17.G.{1,2,4}.3 — advertiser→validate, userspace→routable_addrs, web.py→probe — are absent. Closure on cbt.5/.6/.8 should not be claimed until wiring lands. cbt.7 is partially shipped (schema only, no resolve-side population).

---

## (a) Shipped behaviors that match spec

### cbt.8 / §17.G.4 — TXT validation module
- `saturn/mdns/txt.py:1` — `TXT_SAFE_CEILING = 1200` matches §17.G.4.2.
- `saturn/mdns/txt.py:4` — `class TxtTooLarge(ValueError)` matches.
- `saturn/mdns/txt.py:8-21` — `validate(props) -> int`: per-entry 255-byte cap (RFC 6763 §6.1) + total-ceiling check. Implementation matches §17.G.4.2 surface.
- Tests at `saturn/tests/test_txt_validate_cbt8.py` exercise all three failure modes (under-ceiling pass, oversize-individual, oversize-total). ✅

### cbt.6 / §17.G.2 — routable_addrs module
- `saturn/mdns/interfaces.py:7-21` — `routable_addrs() -> List[str]` filters by `psutil.net_if_stats().isup`, excludes loopback (`127.`) and link-local (`169.254.`). Matches §17.G.2.2 contract.
- Tests at `saturn/tests/test_routable_addrs_cbt6.py` cover return-type, exclusion rules, and at-least-one-on-typical-host. ✅

### cbt.5 / §17.G.1 — isolation probe module
- `saturn/mdns/isolation.py:13-20` — `IsolationProbe` dataclass fields match §17.G.1.2 (`advertising`, `self_seen`, `peers_seen`, `ifaces_with_link`, `suspected_ap_isolation`, `diagnosis`).
- `saturn/mdns/isolation.py:36-108` — `probe(timeout=4.0)`: registers a transient `_saturn-probe._tcp.local.` advertisement, browses for it, classifies four cases (loopback failed, no-link, AP-isolation suspected, healthy). Matches §17.G.1.2 contract.
- Tests at `saturn/tests/test_isolation_cbt5.py` cover surface + return-type. ✅

### cbt.7 / §17.G.3 — ServiceRecord schema
- `saturn/mdns/backend.py:13` — `ServiceRecord.addresses: list[str] = field(default_factory=list)` matches §17.G.3.2 schema. Back-compat `host: str` retained. ✅ (schema only)

---

## (b) Divergences

### B-1. Module-only ship, no integration (cbt.5, cbt.6, cbt.8) — **REJECT divergence**

Three of the four §17.G items shipped the new module + unit tests but **did not wire the module into the runtime caller specified by §x.3 (Integration)**:

| Bead | Spec wire-in | Status | Citation |
|---|---|---|---|
| cbt.5 | §17.G.1.3: `/api/discover` augments response with `isolation` key | **NOT WIRED** | `saturn/web.py` has no `from saturn.mdns.isolation import probe`; only test files reference it |
| cbt.6 | §17.G.2.3: `UserspaceBackend.advertise` uses `routable_addrs()` for multi-address `ServiceInfo` | **NOT WIRED** | `saturn/mdns/userspace.py:123-125` still calls `get_lan_ip()` then `addr = [socket.inet_aton(host_ip)]` (single address) |
| cbt.8 | §17.G.4.3: `SaturnAdvertiser.register()` calls `validate(self._properties())` before `_backend.advertise(spec)` | **NOT WIRED** | `saturn/discovery.py:521-540` has no `validate(...)` call; goes straight to `_backend.advertise(spec)` |

**Why reject:** the public-API tests are not load-bearing for any user-visible behavior. A regression in the wiring (e.g., someone deletes the planned `validate(...)` call before it's added) would not fail any test. Closure on these beads requires the wire-in landing **plus** an integration test that exercises the runtime path (e.g., bloated TXT registers → `register()` returns `False` and logs `TxtTooLarge`).

### B-2. cbt.7 dual-stack resolve-side **NOT SHIPPED** — REJECT

- Schema field `ServiceRecord.addresses` exists but no backend populates it.
- `saturn/mdns/userspace.py:34-35` still extracts only `info.addresses[0]` via IPv4-only `inet_ntoa`.
- `saturn/mdns/bonjour.py` resolve path unchanged from audit baseline (no `DNSServiceGetAddrInfo`).
- `saturn/mdns/avahi.py` no dual-protocol accumulation.
- Spec §17.G.3.3 explicitly required AAAA extraction across all three backends. Schema-only ship is half a feature.

**Why reject:** consumers reading `service.addresses` will get `[]` everywhere, which is worse than the spec saying "use `host` for back-compat" — it's a correctness footgun.

### B-3. CONFIG_FIELDS additions absent — **ACCEPT for now, file follow-ups**

Spec named three new config knobs:
- §17.G.2.5: `advertise_all_interfaces: bool = True`
- §17.G.3.5: `prefer_ipv6: bool = False`
- §17.G.4.5: `txt_safe_ceiling: int = 1200`

None are present in `saturn/config.py` (verified via grep). For the rough pass this is **acceptable** — the underlying behavior is hardcoded to the safe default the config would have selected anyway (true / false / 1200). File a follow-up bead to add the knobs once the wiring above lands; without wiring, configs would have nothing to configure.

### B-4. isolation `_link_ifaces` does not match spec helper — **ACCEPT**

Spec §17.G.1.2 implies a free function returning interface diagnostics; shipped code uses a private `_link_ifaces()` helper inside `isolation.py:23-33` that returns interface names rather than a structured object. Functionally equivalent for the only consumer (`probe()`); private surface is fine. **Accept** as implementation detail.

### B-5. isolation probe binds loopback rather than `0.0.0.0` — **ACCEPT, document**

`saturn/mdns/isolation.py:43,51` advertises on `127.0.0.1` only. The spec didn't pin this. Loopback-only makes the "self-seen" check unambiguous (no false negatives from firewall on real iface) but means the probe cannot detect "I can advertise on lo but not on wlan0" — only "zeroconf engine works at all." For the AP-isolation use case (the primary motivator), this is fine because the heuristic is `self_seen=True AND peers_seen=0 AND ifaces_with_link>=1`. **Accept**, but flag in code comment.

---

## (c) Spec items NOT shipped — propose new beads

These should land before claiming closure on cbt.5/.6/.7/.8:

### NEW: Saturn-cbt.5.1 — wire `isolation.probe()` into `/api/discover`
- File: `saturn/web.py` `/api/discover` handler (currently `saturn/web.py:614-633`).
- Change: call `probe(timeout=4.0)` once per request (or cache for 30s); add `isolation` key to JSON response per §17.G.1.3.
- Plus Web-UI: `Web-UI/app.js:946` conditional render per §17.G.1.4.
- Test: integration hit `/api/discover` while advertising; assert `isolation.diagnosis` present.

### NEW: Saturn-cbt.6.1 — wire `routable_addrs()` into `UserspaceBackend.advertise`
- File: `saturn/mdns/userspace.py:121-138`.
- Change: replace single-address `addr = [socket.inet_aton(host_ip)]` with `addrs = [socket.inet_aton(ip) for ip in routable_addrs()] or [socket.inet_aton(get_lan_ip())]`.
- Test: real multi-NIC harness (qj5.7) — advertise from server, browse from clients on each subnet, both must see the service. **No mocks** per RUN_BRIEF_MAY05 hard rule.

### NEW: Saturn-cbt.7.1 — populate `ServiceRecord.addresses` across all backends
- Files: `saturn/mdns/userspace.py:28-47`, `saturn/mdns/bonjour.py:359-398`, `saturn/mdns/avahi.py:207-224`.
- Userspace: collect both AF_INET (4-byte) and AF_INET6 (16-byte) entries from `info.addresses` via `inet_ntoa` / `inet_ntop` respectively.
- Bonjour: chain `DNSServiceGetAddrInfo` after resolve to fetch A+AAAA.
- Avahi: accumulate across `AVAHI_PROTO_INET` and `INET6` callbacks.
- Test: dual-stack harness; assert both v4 and v6 strings in `addresses`.

### NEW: Saturn-cbt.7.2 — advertise-side AAAA records
- File: `saturn/mdns/userspace.py:121-138` (extends cbt.6.1).
- Change: `routable_addrs()` extends to dual-stack (return v4 + v6 mix); pass via `addresses=` to `ServiceInfo`.
- Test: advertise on dual-stack host; resolve returns both record families.

### NEW: Saturn-cbt.8.1 — wire `txt.validate()` into `SaturnAdvertiser.register()`
- File: `saturn/discovery.py:521-540`.
- Change: insert `validate(self._properties())` before constructing `AdvertiseSpec`. On `TxtTooLarge`, attempt prune of `models` → `capabilities` → `features` per §17.G.4.3 fail-loud step.
- Test: register with bloated `models` list → `register()` returns True with `mtrunc=1` flag set; pathological props → returns False with logged `TxtTooLarge`.

### NEW: Saturn-cbt.G.cfg — CONFIG_FIELDS additions
- File: `saturn/config.py`.
- Add: `advertise_all_interfaces`, `prefer_ipv6`, `txt_safe_ceiling` per §17.G.{2,3,4}.5.
- Wire each into the respective consumer (`UserspaceBackend.advertise`, client connection ordering, `txt.validate` ceiling parameter).

---

## Closure recommendation

| Bead | Status | Recommendation |
|---|---|---|
| cbt.3 (audit only) | Spec'd | Closeable on rough-pass acceptance + memo of MAX_REJECTED correction |
| cbt.5 | Module + tests only | **Do not close.** Block on cbt.5.1 |
| cbt.6 | Module + tests only | **Do not close.** Block on cbt.6.1 |
| cbt.7 | Schema only | **Do not close.** Block on cbt.7.1 + cbt.7.2 |
| cbt.8 | Module + tests only | **Do not close.** Block on cbt.8.1 |

Suggested wire-in order (lowest-risk first): **cbt.8.1 → cbt.5.1 → cbt.6.1 → cbt.7.1 → cbt.7.2 → cbt.G.cfg.**

## Hand-off

Athena: route cbt.{5,6,7,8}.1 wire-in beads to hardener with brutus authoring contracts. cbt.G.cfg can wait until wire-ins land (no point configuring nothing).

Full pass deferred — would add: real harness measurements for cbt.6.1 multi-NIC, screen capture of Web-UI rendering the AP-isolation diagnosis from cbt.5.1.
