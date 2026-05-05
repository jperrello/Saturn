# CONTRACT — Saturn-cbt.3.a: settle_time plumbing in `discover()`

**Status:** RED. 1 test pinned. Behavior is missing.
**Implementer:** athena will route (recommended: hardener — ~1-line plumb).

## Decomposition note

Saturn-cbt.3 is a 4-part audit (DISCOVERY_AUDIT.md areas a/b/c/d). Brutus
refused to bundle. Geoff's suggested order: a → c → d → b. Each gets its own
contract.

- **cbt.3.a** — settle_time plumbing (this contract).
- **cbt.3.c** — known_nodes cross-process safety (next).
- **cbt.3.d** — discover() max_age / liveness sweep (after .c).
- **cbt.3.b** — userspace parallel resolves (last; biggest blast radius).

## Spec restatement (falsifiable)

`saturn.discovery.discover(timeout, settle_time)` (`saturn/discovery.py:275`)
currently constructs `SettleDetector()` with no arguments, so the hardcoded
`timeout=0.5` in `saturn/mdns/settle.py:5` always wins; the caller's
`settle_time` is silently ignored.

The fix MUST plumb the caller's `settle_time` through, so that:

- `discover(timeout=5.0, settle_time=3.0)` against a network with one
  advertised service takes **≥2.5s** (proves the 3s settle is in effect).
- Total elapsed MUST stay below the `timeout` cap (`<6.0s` with slack).

## Test files

- `saturn/tests/test_discovery_settle_cbt3a.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_discovery_settle_cbt3a.py --no-header -rN --tb=short
```

No external dependency — uses Zeroconf on loopback (`interfaces=["127.0.0.1"]`).

## Captured red output

```
saturn/tests/test_discovery_settle_cbt3a.py:75: AssertionError: discover(
  timeout=5.0, settle_time=3.0) must respect the caller's settle_time and wait
  at least ~3s after the last add; took 0.53s.
========================= 1 failed, 1 warning in 2.83s =========================
```

Full transcript: `.brutus/Saturn-cbt.3.a/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| Service is discoverable at all | `len(found) >= 1` for the registered name |
| Lower bound on elapsed | `elapsed >= 2.5` (proves settle_time honoured) |
| Upper bound on elapsed | `elapsed < 6.0` (still bounded by `timeout`) |

## Fix sketch (non-binding)

`saturn/discovery.py:280`:

```python
settle = SettleDetector(timeout=settle_time)
```

That's the entire change. ~1 line.

## Out of scope

- Plumbing `settle_time` to anywhere else (only `discover()` is in scope).
- Adding `max_wait` cap (DISCOVERY_AUDIT.md's separate suggestion — file as
  cbt.3.a.maxwait if wanted).
- Hooking `'removed'` events to settle (cbt.3.x in audit).
- Any other audit area (b/c/d are separate brutus contracts).

## Implementer

athena will route. Suggested: **hardener**. ETA: <5 min.

## Transcript

`.brutus/Saturn-cbt.3.a/transcript.md`
