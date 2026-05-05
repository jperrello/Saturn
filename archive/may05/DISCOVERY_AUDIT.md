# DISCOVERY_AUDIT.md — Saturn-cbt.3 (rough pass)

Branch: `autonomous/promo-push` · Author: geoff · Date: 2026-05-05

Audit of `saturn/discovery.py` + `saturn/mdns/` covering four areas requested by RUN_BRIEF_MAY05 §B.1. Implementer notes carry file:line cites for direct hand-off to brutus contract authoring.

---

## (a) Settle detection

### Current behavior
- `discover()` instantiates `SettleDetector` and arms it on every `'added'` event (`saturn/discovery.py:275-290`).
- `SettleDetector.__init__` hardcodes `timeout=0.5` (`saturn/mdns/settle.py:5`). The `settle_time` parameter on `discover()` (line 275) is **never plumbed through** — vestigial dead code.
- `arm()` cancels any existing timer before starting a new one (Saturn-pgt fix, `saturn/mdns/settle.py:10-15`); timer is `daemon=True`.
- Removals do **not** call `arm()` — only adds reset the quiet-period timer (`saturn/discovery.py:282`).

### Churn analysis
- **Rapid add/remove of the same node:** safe; removals are no-ops for settle, so the 0.5s window only counts adds. After the last add, settle fires 0.5s later regardless of intervening removes.
- **Continuous adds (>2/sec):** settle never fires until churn pauses; `discover()` blocks until `timeout` (default 8s) and returns whatever is in the cache at deadline. Acceptable but undocumented.
- **Hidden coupling to caller-provided `settle_time`:** callers currently believe they are tuning settle time but are not. Several callers in tests pass non-default values (verify via grep) — silently ignored.

### Implementer notes (for brutus contract)
1. **Plumb `settle_time` through to `SettleDetector(timeout=settle_time)`** — `saturn/discovery.py:280`.
2. **Add a `max_wait` cap** distinct from quiet-period timeout — protects against infinite churn on busy networks.
3. **Hook `'removed'` events to a separate "stability" signal** if we ever want to wait for net-zero churn (out of scope for cbt.3 rough pass; file as cbt.3.x).
4. **Test invariants:**
   - `discover(timeout=2.0, settle_time=0.3)` on a quiet network returns in ~0.3s after first add (currently ~0.5s).
   - `discover(timeout=2.0)` on a churning network (add/remove every 100ms) returns at the timeout, not earlier, with the latest snapshot.

---

## (b) Parallel resolves

### Current behavior
**Bonjour (`saturn/mdns/bonjour.py:329-333`):** browse callback spawns one `daemon=True` thread per service for resolve. Threads block in `select.select(fd, ..., 5.0)` (line 393) → `DNSServiceProcessResult` (line 395). Effectively parallel **per-service**, but **unbounded thread count** under burst.

**Userspace (`saturn/mdns/userspace.py:28-47`):** `_resolve()` calls `Zeroconf.get_service_info(type_, name)` (line 29). This is a **synchronous blocking call** invoked from the zeroconf library's add/update callback thread (lines 56, 61). Multiple services serialize on the zeroconf event loop.

**Discovery dispatch (`saturn/discovery.py:182-187`):** `_on_event()` processes events one at a time in whatever thread the backend dispatched from. No batching, no executor.

**Hostname → IP:** `socket.gethostbyname()` (`saturn/discovery.py:420`) is only called by `get_lan_ip()` during advertiser startup, not on the discovery hot path. Resolves come back as IP strings already (Bonjour: `_resolve_service` extracts `host` string at line 367; Userspace: `inet_ntoa(info.addresses[0])` at line 34).

### Profile estimate (rough)
- Bonjour resolve worst-case: 5s `select` timeout × N services serially → catastrophic. Currently parallel-per-service mitigates this.
- Userspace resolve worst-case: zeroconf internal timeout (default 3s) × N services **serialized** in the callback thread → 3N seconds for N flapping services.

### Implementer notes (for brutus contract)
1. **Userspace: dispatch resolve to a `ThreadPoolExecutor(max_workers=8)`** keyed by service name. Drop duplicate in-flight resolves. Cite: `saturn/mdns/userspace.py:56-61`.
2. **Bonjour: cap thread fan-out** with a `BoundedSemaphore(16)` around the resolve thread launch. Cite: `saturn/mdns/bonjour.py:329-333`.
3. **No asyncio retrofit** — keep threads. The library boundaries (`pyobjc`/`ctypes` for Bonjour, `zeroconf` lib for userspace) are sync; mixing event loops here is a tarpit.
4. **Test invariants:**
   - 50 services advertise simultaneously on userspace backend → `discover(timeout=8)` returns ≥48 of them.
   - Thread count delta under burst stays bounded (assert `threading.active_count()` < 32 at peak).

---

## (c) Identity collision under churn

### Current behavior
- `saturn/mdns/known_nodes.py` stores TOFU pins in `~/.saturn/known_nodes.json`.
- **Atomic write:** `save()` uses tmp+rename (`saturn/mdns/known_nodes.py:52-57`). `os.replace(tmp, PATH)` is POSIX-atomic.
- **In-process locking:** module-level `_lock = threading.Lock()` (line 17). All mutators (`pin`, `record_rejection`, `known_node_id`) acquire it for the full load→modify→save cycle (lines 63, 69, 89, 113, 122, 136).
- **Pending pin gating:** `discover()` requires `PIN_CONFIRMATIONS` (Saturn-qj5.16.13.3 deferred TOFU) before calling `pin()` — `saturn/discovery.py:201`.

### Churn analysis
- **Single-process rapid add/remove of same node_id:** safe. Pin only fires after N confirmations; rejections logged via `record_rejection()` under the same lock. No file corruption.
- **Cross-process race:** **theoretical hazard.** No `fcntl.flock` or `O_EXCL` lock on the JSON file. If two Saturn instances run on the same machine (e.g., two `python -m saturn` clients), interleaved `save()` calls race — last-writer-wins, but each save is atomic, so no malformed JSON. Worst case: one process's pin is dropped.
- **`rejected` list growth:** ~~appends without bound~~ — see Addendum 1 below; trim already exists. Real concern is dedupe-by-`(name, node_id)` since the 50-entry FIFO can re-add the same pair under oscillating rebind.

### Implementer notes (for brutus contract)
1. **Add `fcntl.flock` around load+save cycle** for cross-process safety. Cite: `saturn/mdns/known_nodes.py:52-57`.
2. **Dedupe `rejected` list by `(name, node_id)`.** A 50-entry trim already exists (`saturn/mdns/known_nodes.py:15,107-108`); see Addendum 1. The remaining gap is content dedupe so an oscillating rebind doesn't push useful older rejections out of the FIFO with redundant copies.
3. **Test invariants (no mocks):**
   - Spawn 4 worker threads each calling `pin()`/`record_rejection()` 250x with churning node_ids → final JSON parses cleanly, total nodes ≤ unique inputs.
   - Spawn 2 subprocess clients each pinning 100 distinct nodes → final state contains all 200 (currently may lose ~5-10 to cross-proc race).

---

## (d) Cache strategy / TTL

### Current behavior
- **No `discover()` result cache.** Each call constructs a fresh `SaturnDiscovery`, blocks for settle, returns snapshot, calls `stop()` (`saturn/discovery.py:275-290`).
- **`SaturnDiscovery.services` dict** persists for the lifetime of the instance (`saturn/discovery.py:136-150`). No TTL, no periodic sweep.
- **Removal triggers:** only the backend's `'removed'` event (`saturn/discovery.py:187`). Backends:
  - Userspace: zeroconf library emits removal when the goodbye packet arrives **or** the record's mDNS TTL expires (zeroconf manages TTL internally).
  - Bonjour: `dns_sd` daemon emits removal on goodbye / TTL expiry.
- **Effective TTL = whatever the underlying mDNS library decides.** Saturn does not parametrize it.

### Risk: zombie services
- If a peer crashes hard (no goodbye) and the LAN drops the ARP entry, the entry persists in `services` dict until the underlying library's TTL sweep. For zeroconf, default record TTL is 120s (4500s in some configs); for Bonjour, default is 75 minutes for service records.
- Long-lived `SaturnDiscovery` (e.g., the runner's continuous browser) can accumulate ghost entries.

### Implementer notes (for brutus contract)
1. **Document the actual cache contract** in `saturn/discovery.py` module docstring (per project rules, single-line comment only): `# services dict expires entries via backend goodbye/TTL — no Saturn-level sweep`.
2. **Add liveness probe sweep** — every 30s, `/v1/health` ping each cached service; drop on 2 consecutive failures. **Cross-references cbt.4** (failover health-loop already lives there). Coordinate with cbt.4 owner to share the probe.
3. **Expose a `max_age` arg on `discover()`** that filters out entries older than N seconds based on `last_seen` timestamp on `SaturnService`.
4. **Test invariants (no mocks):**
   - Advertise on port A, kill the advertiser hard (SIGKILL, no goodbye), call `discover(max_age=10)` → entry absent within 10s.
   - Long-running `SaturnDiscovery` over 5min on a churning network → `services` dict size matches active services within ±1.

---

## Summary risk matrix

| Area | Severity | Bead |
|---|---|---|
| (a) Settle — `settle_time` not plumbed | Low (silent ignore) | cbt.3 |
| (b) Parallel resolves — userspace serial | Medium | cbt.3 |
| (c) Identity — cross-proc lock missing | Low–Medium | cbt.3 |
| (d) Cache — no TTL/liveness sweep | Medium | cbt.3 (coord cbt.4) |

## Hand-off

Brutus: contract these as four sub-deliverables under cbt.3. Suggested order: (a) → (c) → (d) → (b). (b) last because it's the largest blast radius and benefits from the test scaffolding (a) lays down.

Full pass refinements queued: profile numbers (real measured), demo capture for churn test, RUN_BRIEF_MAY03 §6.1 cross-reference paragraph.

---

## Addendum 1 — MAX_REJECTED correction (2026-05-05)

The rough-pass §(c) claim that `rejected` grows unbounded was **wrong**. `saturn/mdns/known_nodes.py:15` defines `MAX_REJECTED = 50`, and `record_rejection()` enforces it at lines 107-108: `if len(state["rejected"]) > MAX_REJECTED: state["rejected"] = state["rejected"][-MAX_REJECTED:]`. The list is a FIFO trimmed to the most-recent 50 entries on every append. The remaining (real) concern is that the trim does **not dedupe by `(name, node_id)`**, so an oscillating rebind can push useful older rejections out of the window with redundant copies of the same offender — that's the gap implementer note §(c).2 should target. The atomic-write + in-process lock + cross-process lock findings are unchanged. Brutus flagged this; correction folded so the audit reflects reality. — geoff
