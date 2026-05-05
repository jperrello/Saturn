# CONTRACT — Saturn-vyy / cbt.cross-client.real: protocol-level cross-client

**Status:** GREEN on first run. **Regression-guard contract** (per CHEATSHEET §2). Proof, not bug fix.
**Implementer:** none required.

## Spec restatement (falsifiable)

Saturn-ggn (cbt.cross-client) was an HTTP-stack-parity guard over `/v1/*`
JSON shapes. THIS contract proves the deeper claim:
**Saturn is a protocol, not a Python package.**

A service registered by `SaturnAdvertiser` MUST be observed by three
independent stacks:

  1. **Python `zeroconf`** — different code path than Saturn's own
     `SaturnDiscovery` (raw `Zeroconf` + `ServiceBrowser`).
  2. **`dns-sd -B`** subprocess — Apple's reference Bonjour CLI, written
     in C against `mDNSResponder`. Conformance signal for the wire format.
  3. **`curl`** — hits the advertised IP:port. Closes the loop on "the
     protocol is usable end-to-end from a non-Python HTTP client."

If all three observe the same registered service, Saturn's mDNS is
spec-compliant.

## Test files

- `saturn/tests/test_cross_client_real_vyy.py` (added; 1 test, 3 sub-asserts).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_cross_client_real_vyy.py --no-header -rN --tb=short
```

macOS only — skipped on hosts without `dns-sd`. Linux equivalent filed as
**Saturn-vyy.linux** (avahi-browse).

## Captured first-run output

```
saturn/tests/test_cross_client_real_vyy.py . [100%]
========================= 1 passed, 1 warning in 5.36s =========================
```

Three independent stacks all see the registered Saturn service.
Transcript: `.brutus/Saturn-vyy/transcript.md`.

## Why no red phase

Saturn's `SaturnAdvertiser` already publishes a spec-compliant
`_saturn._tcp.local.` SRV+TXT record via the userspace zeroconf backend.
Apple's `mDNSResponder`, Python's `zeroconf` library, and `curl`'s
HTTP-on-loopback all consume those records / the advertised endpoint
unchanged. The protocol claim holds today; this contract pins it so a
future refactor (e.g., switching backends, custom SRV target munging,
non-default service-type strings) cannot silently regress the
"protocol-not-package" guarantee.

## Oracle definition

| Vehicle | Oracle |
|---|---|
| Python `zeroconf.ServiceBrowser` | service instance name appears in `add_service` callbacks within 5s |
| `dns-sd -B _saturn._tcp local` | stdout contains `Add\s+\d+\s+\d+\s+local\.\s+_saturn\._tcp\.\s+<name>` within 3.5s |
| `curl -sS http://127.0.0.1:<port>/health` | exits 0 with HTTP status in `[200, 500)` |

## Out of scope

- Linux variant via `avahi-browse` → **Saturn-vyy.linux**.
- Cross-host (LAN) browse — needs harness with two real machines or
  veth-pair setup. File as **Saturn-vyy.lan** if/when infrastructure
  lands.
- Go (`net/http` + a Go mDNS browser) → **Saturn-ggn.go** stretches to
  cover the protocol angle if a Go mDNS lib is wired in.
- Bonjour CLI flags beyond `-B` (e.g., `-Z` for full record dump).
- IPv6 service browse (only IPv4 advertise tested here; IPv6 advertise
  side is **Saturn-9rv** territory).

## Implementer

None. Brutus attests the regression guard. Athena: file Saturn-vyy.linux
when an avahi-browse environment is available.

## Transcript

`.brutus/Saturn-vyy/transcript.md`
