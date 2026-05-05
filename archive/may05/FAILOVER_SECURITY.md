# FAILOVER_SECURITY.md — security audit, cbt.4 + wave-2 mDNS

Branch: `autonomous/promo-push` · Author: geoff · Date: 2026-05-05 · Pass: rough

Scope: `/api/system/chat` (cbt.4 client-side failover), `X-Saturn-Conversation-Id` sticky session, `saturn_meta.routing.events` envelope, AAAA / IPv6 advertise (cbt.7.advertise wave-2), and `/api/discover` augmented with isolation key (cbt.5.1 spec; not yet shipped).

## Headline

One **P1** finding (filed as bead): **Saturn-zd6** — `_failover_state` dict at `saturn/web.py:149` is an unbounded conversation-ID → peer-name map with no TTL or LRU. Trivial DOS via header spray. Three **P2/P3** findings inline below. AAAA filtering for v6 advertise is **partially correct** — link-local + loopback excluded, but ULA / temp-privacy scopes are not, and case-sensitive `fe80:` match misses uppercase.

---

## (1) `/api/system/chat` — auth, limits, payload

### Findings
- **No auth.** Handler at `saturn/web.py:1062-1063` accepts any HTTP request that can reach the bound port. By design Saturn is LAN-trust, but the surface is exposed to anyone on-LAN who can hit the port.
- **Per-IP rate limit OK.** `SATURN_RATE_RPM=30`, TPM cap 100k, concurrency 3 — `saturn/web.py:228-230`, enforced at `:1064-1067`.
- **No message-array bound.** `BrutusChat.messages: List[dict]` at `saturn/web.py:1035-1060` has no `max_items` validator. A single request with a 100k-element messages list passes validation and is forwarded to `_adapt()` at `:1180`, then to upstream LLM. Memory pressure scales with N×payload. **P3** — rate limit caps overall damage, but a single bad-faith client within their RPM allowance can pin RAM.
- **Body size cap relies on FastAPI default** (~no enforced cap unless explicitly set in `Starlette` middleware; not set in saturn). **P3.**

### Remediation (inline, no bead yet)
- Add `Field(max_items=100)` on `BrutusChat.messages`.
- Add explicit `MAX_BODY_BYTES = 1_000_000` middleware check.
- Defer auth retrofit to a future `auth-on-LAN` epic — out of scope for cbt.4.

---

## (2) `X-Saturn-Conversation-Id` sticky session

### Finding — **P1, filed as Saturn-zd6**
`_failover_state: dict[str, str]` at `saturn/web.py:149`. Unconditionally inserted at `:1209` keyed by client-supplied `convo_id`. **No TTL, no LRU, no max-size.**

```python
_failover_state: dict[str, str] = {}  # conversation_id -> peer_name (sticky)
...
_failover_state[convo_id] = c["name"]   # web.py:1209
```

### Attack
Loop `curl -H "X-Saturn-Conversation-Id: $(uuidgen)" /api/system/chat` per the IP rate limit (30 RPM × N IPs). The dict grows monotonically. Memory cost per entry is small (~150B for UUID + name), but at 30 RPM × 60 min × 24 h × 7 days × M attackers, the dict reaches millions of entries — measurable OOM well before that. Even short of OOM, the dict starts to dominate process working-set and degrade everything else.

### Secondary risk — sticky pin manipulation
A malicious client can also **stick a conversation to a specific peer** by guessing/spraying convo_ids until one lands on the highest-priority peer, then reuse it. Not directly destructive but undermines the failover contract (sticky should follow legit client conversation continuity, not adversarial pinning).

### Remediation
- `OrderedDict` with `MAX_STICKY = 10_000` and LRU eviction on insert.
- Per-entry TTL (suggest 1 hour — matches typical chat session length); background reaper or check-on-access.
- Optional: bound per-IP convo_ids to e.g. 100 active sticky entries.

Bead **Saturn-zd6** filed under cbt epic, P1.

---

## (3) `saturn_meta.routing.events` — info leak

### Finding — P2

`routing.events` envelope built at `saturn/web.py:1140` and yielded at `:1245`:
```python
events.append({"from": prev_name, "to": c["name"], "reason": prev_reason, "at": time.time()})
meta["routing"]["service"] = chosen["name"]
```

Reasons exposed (saturn/web.py:1154, 1174, 1176, 1194, 1202, 1204):
`"health_timeout"`, `"active_5xx"`, `"no_models"`, `"http_<status>"`.

Service names are operator-chosen labels (e.g., `llama-gpu-1`, `ollama-edge`). Returned verbatim in the receipt. An attacker can:
1. Enumerate peers by initiating chats and reading the receipt — gets a roster of service names.
2. Trigger failover (e.g., flood one peer to its TPM cap) and watch the `events` stream to confirm which secondary peer takes over.
3. Build a topology + priority map of internal infra without ever hitting `/api/discover`.

### Remediation (inline)
- Hash service names in `events` (`hashlib.blake2s(name, digest_size=8).hexdigest()`); the **same hash** stays stable for the duration of a conversation so the receipt is still useful for debugging continuity.
- Reduce reason granularity for unauth callers: keep `"unavailable"` external, log full reason internally.
- Saturn is LAN-trust, so this is **P2** rather than P1. File as `Saturn-csec.2` if athena wants tracked separately; otherwise fold into cbt.4 hardening sweep.

---

## (4) AAAA / IPv6 advertise — scope filtering

### Current state (verified `saturn/mdns/interfaces.py:7-29`)
```python
elif a.family == socket.AF_INET6 and want_v6:
    bare = ip.split("%", 1)[0]
    if bare in ("::1", "::") or bare.startswith("fe80:") or bare.startswith("FE80:"):
        continue
    out.append(bare)
```

Wave-2 has begun shipping v6 support. `routable_addrs(family="both")` filters loopback (`::1`, `::`) and link-local (`fe80::/10`, both cases). **What's missing:**

### Finding — P2

| Scope | Filtered? | Risk |
|---|---|---|
| Loopback `::1`, `::` | ✅ | — |
| Link-local `fe80::/10` | ✅ (case-checked) | — |
| ULA `fc00::/7` (`fc..`/`fd..`) | ❌ | **Leak**: ULA is private but routable across an org's L3 fabric. Advertising it via mDNS is correct **if** ULA is the intended LAN scope, but Saturn has no signal for that — currently it would advertise ULA addrs as if they were globally usable. Mostly cosmetic but can confuse multi-segment deployments. |
| Temp-privacy / SLAAC temporary | ❌ | **Leak**: Linux/macOS rotate these. Advertising one freezes a rotating identifier into peer pin caches; defeats the privacy mechanism. |
| Deprecated (`tentative`/`deprecated` flags) | ❌ | **Stale advertise**: `psutil` doesn't expose v6 flags; advertising a deprecated address means clients connect and fail. |
| 6to4 `2002::/16`, Teredo `2001::/32` | ❌ | **Tunnel leak**: rare, but should not be advertised to LAN peers. |

Case-sensitive `startswith("fe80:")` + `"FE80:"` covers most platforms (psutil/Linux returns lowercase; macOS sometimes mixed case — covered). But if any platform produces `Fe80:` mixed-case, it slips through. Use `bare.lower().startswith("fe80:")` for robustness.

### Remediation (inline)
Extend filter in `interfaces.py`:
```python
b = bare.lower()
if b in ("::1", "::") or b.startswith("fe80:") or b.startswith("fc") or b.startswith("fd"):
    continue
if b.startswith("2002:") or b.startswith("2001:"):  # 6to4 / Teredo — exclude
    continue
```
For temp-privacy, no clean `psutil` signal — recommend documenting "use stable IID" deployment guidance, not code change.

Brutus is briefed on cbt.7.advertise; fold this filter expansion into that contract.

---

## (5) `/api/discover` + isolation key

### Current state
Handler `saturn/web.py:614-636` returns service list with: `name`, `host`, `port`, `priority`, `deployment`, `api_type`, `models`, `node_id`. **No auth.** Augmented (per cbt.5.1 spec) with `isolation: {advertising, self_seen, peers_seen, ifaces_with_link, suspected_ap_isolation, diagnosis}`.

### Finding — P2

The service list itself is **by-design public on LAN** (Saturn is a discovery service; clients need this to connect). Adding `isolation.ifaces_with_link` from `_link_ifaces()` (`saturn/mdns/isolation.py:23-33`) introduces a **new info-leak vector**: interface names like `tun0`, `wg0`, `ppp0`, `utun0` reveal VPN/tunnel presence on the host. `eth0` + `wlan0` reveals dual-NIC. `docker0`, `br-*` reveals containerization.

This is recon, not direct compromise. But Saturn was previously leaking only services-on-LAN; with cbt.5.1, it would also leak host-network-config-on-LAN. That's a category expansion worth flagging.

### Remediation (inline)
Two cheap fixes, either is fine:
- Reduce `ifaces_with_link` to a count (`int`) rather than names. The diagnosis prose can still distinguish "no link" from "AP isolation" without naming the interfaces.
- Or: keep names but only return them when the request originates from `127.0.0.1` (localhost, i.e., the Web-UI on the same host). Cite: `request.client.host` check at handler entry.

The latter is preferable — local Web-UI users get full diagnostics; LAN peers see counts only.

---

## P1 bead filed

**Saturn-zd6** — bound `_failover_state` (TTL + LRU). See bd.

## Inline P2/P3 to fold into wave-2 contracts

| § | Risk | Fix landing site |
|---|---|---|
| (1) message array bound | P3 | `BrutusChat` validator — fold into cbt.4 hardening |
| (3) routing.events name leak | P2 | hash names in receipt — fold into cbt.4 |
| (4) ULA / mixed-case / 6to4 v6 filter | P2 | extend `interfaces.py` filter — fold into cbt.7.advertise (Saturn-9rv) |
| (5) ifaces_with_link leak | P2 | localhost-only or count-only — fold into cbt.5.1 (athena's NEW bead) |

## Hand-off

Athena: route Saturn-zd6 to hardener as P1. Brutus: fold (3), (4), (5) into existing wave-2 contracts (Saturn-pcj / 1xh / bfx / cbt.5.1) — cites are above. Full pass deferred unless wave-2 surfaces a new auth or quota path that warrants re-review.

---

# Full pass — phase 4 (2026-05-05)

Six additional concerns beyond the rough-pass surface. Two new P1 beads filed; four lower findings inline. Findings (A), (B) are exploitable today on any LAN-trust deployment; (C) is borderline P2/P1; (D)(E) are inline P2/P3; (F) verified clean.

## (A) TOFU pin-race — **P1, Saturn-93w**

`saturn/discovery.py:202-213` enters `first_seen` state on unrecognized service-name. After `PIN_CONFIRMATIONS=2` (`saturn/mdns/known_nodes.py:50`) the `node_id` is permanently pinned and subsequent `node_id` mismatches for that name become `rebind_rejected` (`:216-218`) and silently filtered out of `get_all_services()` by the `_SELECTABLE` filter (`:278`).

**Attack:** any host on the LAN can advertise a target service-name with arbitrary `node_id` before the legit peer comes online. Two confirmations within seconds is trivial — same-host self-confirms. Once pinned, the legit peer is **invisible** to the cluster; no log, no alarm, no UI surface.

**Why this is P1 not "TOFU as designed":** Saturn's TOFU lacks any operator pre-seed path. Compare to SSH `known_hosts` (operator-distributable), HSTS preload list (browser-vendor curated), or BLE pairing (out-of-band confirm). Saturn is purely "whoever advertised first" — no operator agency.

**Recommended fix (filed in bead):** wire the `known_nodes` allowlist surface (qj5.16.13 partial) into a `~/.saturn/allowlist.json` operator-asserted name → node_id map, consulted before TOFU promotion. Refuse TOFU pin when name is in allowlist with a different node_id; refuse rebind even if pinned.

**Cites:** `saturn/discovery.py:196-218`, `saturn/discovery.py:278`, `saturn/mdns/known_nodes.py:50,85-102`.

## (B) `api_base` TXT trust — SSRF / route hijack — **P1, Saturn-xqw**

```python
# saturn/discovery.py:175 (resolve)
api_base=props.get('api_base', ''),

# saturn/discovery.py:116-118 (consume — cloud branch)
if self.deployment == "cloud" and self.api_base:
    return self.api_base
```

`runner.py:116-122` consumes `effective_endpoint` for live forwarding without validation. **A peer can advertise `api_base=http://169.254.169.254/` (AWS metadata service) or `http://127.0.0.1:9200/` (internal Elastic) or `http://evil.example/` (off-LAN exfil).**

**Why this is P1:** chat content + any forwarded headers (including bearer tokens used for upstream auth) flow to attacker-controlled URL. No detection. The `deployment="cloud"` gate is **also peer-asserted** in TXT — a peer can self-elevate to cloud-deployment trust by simply setting that key.

**Recommended fix (filed in bead):**
1. **Advertise-side:** sanitize `api_base` (currently NOT sanitized — see §(D)). Require scheme `https://` for cloud-deployment; reject any `api_base` whose host resolves to RFC-1918/loopback/link-local/CGNAT/IPv6 ULA.
2. **Consume-side:** re-validate on resolve — both before adding to `services` dict and before any forward. The `effective_endpoint` accessor at `saturn/discovery.py:116` is the single point to gate.
3. **Document trust model:** `api_base` MUST be operator-asserted (e.g., signed TXT or whitelisted source); peer-asserted is unsafe.

**Cites:** `saturn/discovery.py:116-118,175`, `saturn/runner.py:116-122`.

## (C) `/api/discover` probe DoS amplification — P2 (borderline)

`/api/discover` at `saturn/web.py:661-683` is **not rate-limited** (no `_check_rate(ip)` call; contrast `/api/chat` at `:990`, `/api/proxy/chat` at `:937`, `/api/system/chat` at `:1113`). Each request runs `discover(timeout=5.0)` + `isolation.probe(timeout=4.0)` ≈ **9 s of blocking work and one mDNS register/unregister cycle**.

10 parallel requests = 90 process-seconds of work + 10 transient mDNS announcements per cycle. Multiply by attacker count.

**Fix (inline, fold into cbt.5.1):** add `_check_rate(ip)` to `/api/discover`; cap probe-rate to once per 30s per IP via a small in-memory cache; serve cached `isolation` between calls. Spec change to cbt.5.1 only — wire-up still gated on athena's existing bead.

## (D) TXT control-character partial sanitization — P2

`_sanitize_txt_value` at `saturn/discovery.py:480-483` strips `=`, `\x00`, `\n`, `\r`, but is applied **only to `models`** (`:528`). Other TXT values — notably `api_base`, `api_type`, `version`, `deployment` — are passed through unsanitized. `_encode_txt` at `saturn/mdns/bonjour.py:83-89` does no escaping.

Combined with §(B), an attacker can advertise `api_base=http://evil/\nmodels=gpt-x` to force a malformed wire record that some implementations may parse permissively into adjacent fields. No JSON injection observed today (TXT values are treated as strings, split on first `=` and on commas), but the assumption is fragile.

**Fix (inline, fold into cbt.7.advertise / Saturn-9rv contract):** apply `_sanitize_txt_value` to **all** `_properties()` outputs, not just `models`. Add a per-pair length assert to `_encode_txt` for defense-in-depth.

## (E) CSRF — verified safe-by-default, P3 ack

`/api/system/chat` requires `Depends(require_admin)` (`saturn/web.py:1110-1111`); admin token is `Authorization: Bearer …`, not a cookie, so it is not auto-sent on cross-origin POST. No `CORSMiddleware` configured — cross-origin reads are blocked at the browser. Safe **by current default**. **Caveat:** if an operator later adds permissive CORS, the bearer-not-cookie property still helps but a JS-on-LAN attacker who can read `localStorage` (XSS) breaks the property. No code change needed today; document the auth-header invariant in the security posture doc.

## (F) Subprocess injection — verified clean

All `subprocess.Popen` calls in `saturn/web.py` (lines 572-576, 1425-1426, 1473-1475) use list args, no `shell=True`, no peer-derived input. `saturn/discovery.py` imports subprocess but no `dns-sd` shell-out in production paths. **No finding.**

---

## Phase-4 summary

| § | Severity | Bead / fold |
|---|---|---|
| (A) TOFU pin-race | **P1** | **Saturn-93w** |
| (B) `api_base` SSRF | **P1** | **Saturn-xqw** |
| (C) `/api/discover` DoS amplification | P2 | inline → cbt.5.1 contract |
| (D) TXT control-char (api_base + others unsanitized) | P2 | inline → Saturn-9rv (cbt.7.advertise) |
| (E) CSRF | P3 ack | inline; document invariant |
| (F) subprocess injection | None | — |

## Hand-off

Athena: route Saturn-93w + Saturn-xqw to brutus front-of-queue (P1, P1). Both are exploitable from any host on the LAN today. (C) (D) get folded into existing wave-2 contracts (cbt.5.1, Saturn-9rv).
