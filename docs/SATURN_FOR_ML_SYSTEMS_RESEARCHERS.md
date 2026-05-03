# Saturn for ML Systems Researchers

A protocol-level approach to LAN-scoped AI service discovery, with a thesis behind it and a working artifact on a $20 router.

> **Status.** Master's thesis (UC Santa Cruz, Joey Perrello / Adam Smith), in submission. Evaluation is analytical: cognitive walkthrough plus structured threat analysis, not user study or production telemetry. Citations below reference the source manuscript by line range.

---

## 1. The problem

Access to LLM inference is gated by per-application credentials. A household running ChatGPT, Claude, GitHub Copilot, and a half-dozen agent-flavored CLIs holds a separate subscription or API key for each. A small lab provisioning OpenAI for ten graduate students manages ten keys, ten billing relationships, and a ten-line spreadsheet of who-spent-what. An open-source maintainer who wants to add an AI feature has three options: ship the feature behind the user's own key (raising onboarding cost), eat the inference bill (raising financial risk), or skip the feature. Each path pushes credential and billing complexity into the application layer, where it does not belong.

The credential side of this scaffolding leaks in predictable ways. Meli, McNiece, and Reaves (2019) scanned a billion GitHub commits and found that 81% of detected secrets are still valid more than a week after disclosure — the dominant failure mode is *not* discovery, it is the absence of revocation. Static, long-lived API tokens widely distributed across user devices and developer machines maximize exposure to exactly this failure mode. *Saturn.md:609–625, 1334–1344.*

Billing fragmentation amplifies the problem. Provisioning N applications and M users at a traditional vendor takes on the order of `12 + 19N + 7M` configuration steps under the cognitive walkthrough in *Saturn.md:1191–1224* — the linear `19N` term is dominated by Stripe / billing scaffolding the developer has to build *per application* even when none of it is on the inference critical path.

## 2. The layer-shift thesis

Saturn's claim is that AI access is mis-layered. Treating an inference endpoint as application-tier state — something each app authenticates to, individually — is the source of the proliferation. Treating it as network-tier state — something the network advertises, the way it already advertises printers, AirPlay receivers, Chromecast targets, and DHCP leases — collapses the configuration surface to one administrative role.

The analogy to Bonjour / DNS-SD is not metaphorical. Saturn is implemented as an mDNS service type (`_saturn._tcp.local.`) advertised with the standard PTR/SRV/TXT triple, discoverable by `dns-sd -B`, `avahi-browse`, or any zeroconf-capable library. The same protocol that lets a phone find a printer without asking the user lets an arbitrary application find an OpenAI-compatible endpoint without asking the user. The abstraction matches the operating reality: in a household, lab, or office, AI is already a shared resource — the protocol simply stops pretending otherwise.

Pushing access to L7 service discovery has a second consequence. Once advertisement is a network primitive, advertisement of *credentials* is a network primitive too. Saturn embeds short-lived JWTs in the TXT field; presence on the network *is* possession of the credential, and absence from the network *is* loss of the credential. This is a different shape of authorization than the bearer-token model the rest of the industry has settled on, and it is the bet on which the security argument turns.

## 3. Protocol

A Saturn service registers under `_saturn._tcp.local.` with the standard DNS-SD record set. TXT carries a small, version-tagged schema:

| Field | Status | Description |
|---|---|---|
| `version` | required | Protocol version (currently `1`) |
| `api_type` | required | `openai`, `ollama`, etc. |
| `deployment` | required | `local`, `cloud`, `network` |
| `priority` | required | Numeric; lower = preferred |
| `api_base` | conditional | Endpoint URL (cloud deployments) |
| `ephemeral_key` | conditional | JWT credential (cloud deployments) |
| `rotation_interval` | optional | Key rotation period in seconds (default 300) |
| `features` | optional | Comma-separated capability flags |

Each TXT string is bounded at 255 bytes by DNS-SD. JWTs fit comfortably; X.509 certificates do not — a constraint that shapes the whole credential design and rules out classes of solutions that look attractive on paper. *Saturn.md:1022–1031.*

Discovery is the standard zeroconf flow: PTR browse, SRV+TXT resolve, sort by `priority`, pick the lowest healthy. All Saturn services expose the same three OpenAI-compatible routes — `GET /v1/health`, `GET /v1/models`, `POST /v1/chat/completions` (SSE-streamed) — so a discovered service is immediately consumable by any OpenAI-SDK-compatible client.

Credential dispensing is handled by *beacons*, a separate role from the inference proxy. A beacon mints a scoped, time-bounded JWT against a cloud provider, embeds it in the `ephemeral_key` TXT field, and rotates every 5 minutes with an overlap window where the current and next keys both validate. Inference traffic does not pass through the beacon; clients read the TXT field and call the upstream API directly. The beacon never sees prompts or completions — a property that matters when reasoning about the threat surface (see §4.3).

## 4. Evidence

Five concrete claims, each grounded in the manuscript.

### 4.1 Cross-language interoperability emerges from the protocol, not a reference SDK

Three reference consumers — Python (`zeroconf`), TypeScript (`multicast-dns`), Rust (`mdns-sd`) — and a fourth path through the macOS `dns-sd` CLI all interoperate against the same advertisement with no shared Saturn-specific code on the discovery side. The wire format is the contract; the libraries are interchangeable. *Saturn.md:1036–1041; Table 4.1, lines 939–965.*

This matters because a protocol-defined contract is what distinguishes Saturn from any number of "AI gateway" SDKs. There is no ABI to track, no SDK version to pin, no language Saturn does not yet support — if a runtime can speak DNS-SD, it can speak Saturn.

### 4.2 The developer-side configuration surface collapses by ~79%

A cognitive walkthrough comparing a per-app provisioning baseline against Saturn discovery, broken out by persona:

| Persona | Traditional | Saturn | Δ |
|---|---:|---:|---:|
| Administrator | 12 | 14 | +17% |
| Application developer | 19 | 4 | **−79%** |
| End user | 7 | 0 | **−100%** |
| Total | 38 | 18 | −53% |

Thirteen of the nineteen developer-side steps are billing / credential-distribution scaffolding that the protocol absorbs into the administrator role. The asymptotic form, over `N` developers and `M` end users, is

```
traditional:  12 + 19N + 7M
Saturn:       14 +  4N + 0M
```

At `N = 10`, `M = 100`, that is `902` traditional steps versus `54` Saturn steps — a 94% reduction at the scaling limit, with the Saturn cost essentially independent of `M`. *Saturn.md:1191–1224; Fig. 5.2, lines 1086–1153.*

This is a structural argument, not a benchmark. It says "we deleted thirteen things you used to have to build," and it is grounded in a concrete, walkable list — which is also why the threats to validity (§5) cut the way they do.

### 4.3 Ephemeral keys bound the dominant secret-leakage failure mode

The Meli et al. result is that 81% of GitHub-leaked secrets are never revoked; the threat surface in the bearer-token regime is dominated by the long tail of stale-but-valid credentials. A Saturn ephemeral key has a 10-minute absolute expiration and rotates every 5 minutes. The window during which a leaked key is exploitable is bounded above by the rotation cycle — a leaked key is dead before any commercial secret scanner can reach it.

The threat-model shift is from internet-scale and unbounded (a key on GitHub is reachable by every actor on the public internet, indefinitely) to LAN-scoped and bounded (a key in a TXT record is reachable only by devices on the broadcast domain, only until rotation). This does not eliminate risk — it changes the shape of the risk, in a direction that is favorable for most realistic deployment targets. *Saturn.md:609–625, 1334–1344.*

### 4.4 One TXT schema covers heterogeneous auth models

The same record set works against three backends with materially different authorization stories:

- **Ollama** — no authentication. `ephemeral_key` absent.
- **DeepInfra** — long-lived static JWT. `ephemeral_key` populated, `rotation_interval` long or omitted.
- **OpenRouter** — short-lived rotating JWT. `ephemeral_key` populated, `rotation_interval` set to the rotation period.

No out-of-band negotiation, no per-vendor TXT extension, no version skew between client and server. This is evidence that the schema generalizes beyond a single vendor's auth idiosyncrasies, which is the test that matters for a protocol claim. *Saturn.md:1022–1031.*

### 4.5 Network-infrastructure-layer deployment is concrete

The Rust implementation cross-compiles to `mipsel-unknown-linux-musl` and runs on a GL-MT300N-V2 — a $20 OpenWRT router with a MIPS32 CPU and 128 MB of RAM — integrated with UCI/LuCI alongside DHCP. The binary is roughly 2 MB with TLS support. *Saturn.md:838–866.*

Two things follow from this. First, "DHCP for AI" is not a slogan — Saturn runs on the same physical box that hands out DHCP leases, in the same configuration system, exposed in the same admin UI. Second, the resource envelope demonstrates that the protocol does not require an x86 server or a containerized control plane; the floor is a sub-watt MIPS device with no swap. Anything heavier is a deployment choice, not a requirement.

## 5. What is *not* claimed

These are surfaced, not buried.

- **Evaluation is analytical.** The step-reduction figures come from a single-author cognitive walkthrough; the security claims come from structured threat analysis. There is no user study, no field deployment, no production telemetry, no benchmark against an existing AI-gateway product. The threats to validity are documented in *Saturn.md:1235–1250*; the most consequential are walkthrough-author bias (the system designer is the one counting steps) and the absence of an empirical baseline distribution. Field evaluation is the obvious next piece of work and is explicitly future work, not deferred-and-implied.
- **AP isolation breaks Saturn.** Enterprise WiFi configurations that block client-to-client multicast — eduroam, most guest SSIDs, hotel networks — render mDNS-based discovery non-functional. This is exactly the deployment environment where the access-equity motivation matters most (a university student on `eduroam` is the canonical user the access argument is meant to serve), and the protocol does not currently work there. A hybrid path that falls back to an HTTPS-based directory under AP-isolation conditions is designed but not shipped. *Saturn.md:1346–1354.*
- **Multicast trust is assumed.** Any device on the broadcast domain can read TXT records, including ephemeral keys. Saturn extends the trust model already implicit in a printer protocol — "if you are on the network, you can use the printer" — to inference. Per-device authentication would void the zero-configuration property that the rest of the design depends on; the trade-off is intentional, but it is a trade-off, and it disqualifies Saturn from threat models where mutually distrusting devices share a LAN.
- **No quality-of-service guarantees.** Priority routing is a soft preference, not an SLA. There is no admission control, no tenant isolation, no token-bucket rate-limiting at the protocol layer. An adversarial or buggy client on the LAN can saturate the priority-1 backend; recovery depends on the backend, not on Saturn.

## 6. Open questions

Three places where outside work would land cleanly.

1. **Empirical evaluation under real network conditions.** The strongest critique of the analytical results is that they assume a working broadcast domain. A measurement study across home networks, university LANs, enterprise WiFi, and consumer-grade mesh routers — characterizing mDNS reachability, TXT record propagation latency, and the failure rate of the discovery flow under realistic radio conditions — would either ground or undermine the protocol claim. The methodology is well-trodden in the wireless-systems literature; the AI-systems framing is new.

2. **Hybrid mDNS / HTTPS directory under AP isolation.** The shipped system fails closed on isolated SSIDs. A directory protocol that preserves the zero-configuration property in the *user* role while admitting a small amount of bootstrap on the *administrator* role (e.g., a captive-portal hint, a `.well-known` URI, a DNS-over-HTTPS fallback) would extend Saturn into the institutional networks where the access-equity argument matters most. The design space is not obvious — most fallback paths break either the credential model or the discovery model — and it is the most consequential piece of unfinished protocol work.

3. **Tenant isolation and adversarial-client behavior.** Saturn currently treats the LAN as a soft-trust environment. A line of work that adds lightweight admission control or token-bucket fairness at the *backend* without imposing per-device authentication at the *protocol* would let Saturn extend into deployment environments (small enterprise, shared coworking, multi-tenant labs) where the printer-trust analogy is too generous. The constraint is keeping the end-user step count at zero; the question is what minimum mechanism preserves it.

A fourth, smaller direction: the credential schema is currently JWT-shaped because of the 255-byte TXT-string limit. There is room for a separate study of what other token formats fit the constraint and whether any of them dominate JWTs on the threat-model dimension that the rotation argument turns on.

---

## References

- Meli, M., McNiece, M. R., & Reaves, B. (2019). *How Bad Can It Git? Characterizing Secret Leakage in Public GitHub Repositories.* NDSS 2019.
- Cheshire, S., & Krochmal, M. (2013). *Multicast DNS.* RFC 6762, IETF.
- Cheshire, S., & Krochmal, M. (2013). *DNS-Based Service Discovery.* RFC 6763, IETF.
- Perrello, J. (in submission). *Saturn: Zero-Configuration AI Service Discovery.* M.S. thesis, UC Santa Cruz. Cited inline as `Saturn.md:<lines>`.
- Repository: <https://github.com/jperrello/Saturn>
- Promo-push framing memo: [`SATURN_CONTEXT.md`](../SATURN_CONTEXT.md) (canonical claim list, used by the writer/demo lanes of this project).
