# CONTRACT — Saturn-9rv / cbt.7.advertise (= geoff's cbt.7.2): advertise-side AAAA records

**Status:** RED. 2 tests pinned.
**Implementer:** athena → hardener.
**Geoff cite:** `PARITY_REVIEW_MAY05.md` §(c) Saturn-cbt.7.2.

## Spec restatement (falsifiable)

Per §17.G.3.3 last paragraph, `SaturnAdvertiser` (via `UserspaceBackend`)
must publish both v4 and v6 routable addresses on the multicast record.
Two surfaces:

1. **`saturn.mdns.interfaces.routable_addrs(family=...)`** — extend with
   a `family` keyword:
   - `family="v4"` (default for back-compat with cbt.6 callers): only
     IPv4 routables.
   - `family="v6"`: only IPv6 routables (`AF_INET6`, excluding link-local
     scope id ambiguity at the caller's discretion).
   - `family="both"`: both, in deterministic order.

2. **`UserspaceBackend.advertise()`** — when both families are available,
   pack 4-byte AF_INET and 16-byte AF_INET6 entries side-by-side into
   `ServiceInfo.addresses`. zeroconf already accepts mixed-length entries
   in the `addresses=` list.

This contract depends on **Saturn-pcj / cbt.6.userspace** wiring `routable_addrs()`
into the advertise path; if pcj has not yet greened, this contract's second
test will also fail on the v4 side. Land pcj first.

## Test files

- `saturn/tests/test_dual_stack_advertise_cbt7_advertise.py` (added; 2 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_dual_stack_advertise_cbt7_advertise.py --no-header -rN --tb=short
```

## Captured red

```
2 failed, 1 warning in 2.04s
advertise must include the v4 routable addr; v4=['192.168.1.13'], v6=[]
```

Transcript: `.brutus/Saturn-9rv/transcript.md`.

## Oracle

| Test | Oracle |
|---|---|
| `routable_addrs_supports_family_kwarg` | `routable_addrs(family="both")` does not raise; returns `list[str]` |
| `userspace_advertise_packs_v4_and_v6` | `info.addresses` decodes to both injected v4 and v6 strings |

Test injects synthetic addrs via Saturn's own helper (test-boundary
control, not external mock).

## Out of scope

- Resolution-side AAAA extraction → **Saturn-1xh / cbt.7.resolve**.
- Bonjour / Avahi advertise paths — daemons handle multi-interface
  natively; only userspace needs the explicit list (§17.G.2.3).
- Link-local scope_id formatting in v6 strings.
- IPv6-only mode (no v4 fallback) — file as **9rv.v6only** if needed.

## Implementer

athena → hardener. ETA ~10 min after pcj lands.
