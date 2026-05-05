# CONTRACT — Saturn-76f / cbt.7.prefer: IPv6 connect-target preference

**Status:** RED. 3 tests pinned.
**Implementer:** athena will route (recommended: hardener — ~10-line helper).

## Spec restatement (falsifiable)

Add `saturn.discovery.connect_address(service: SaturnService) -> str` per
§17.G.3.5. Behavior:

- `SATURN_PREFER_V6` unset / "0" / "false" → return first IPv4 address from
  `service.addresses` (fall back to `service.host` only if `addresses` is
  empty).
- `SATURN_PREFER_V6` set to a truthy value (`"1"`, `"true"`, etc.) → return
  the first IPv6 address (any address containing `:`); fall back to first
  IPv4 if no v6 present.

URL bracketing for v6 hosts (e.g., `http://[fe80::1]:8080/`) is the
caller's responsibility — this helper returns a bare address string.

## Test files

- `saturn/tests/test_prefer_v6_cbt7_prefer.py` (added; 3 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_prefer_v6_cbt7_prefer.py --no-header -rN --tb=short
```

## Captured red

```
3 failed, 1 warning in 0.18s
saturn.discovery must expose connect_address(service) -> str.
```

Transcript: `.brutus/Saturn-76f/transcript.md`.

## Oracle

| Test | Oracle |
|---|---|
| `default_returns_ipv4` | unset env, addresses=["192.168.1.10","fe80::1"] → "192.168.1.10" |
| `prefer_v6_returns_ipv6` | env=1, same addresses → "fe80::1" |
| `prefer_v6_falls_back_to_v4` | env=1, addresses=["192.168.1.10"] → "192.168.1.10" |

## Out of scope

- URL bracketing helpers.
- `SATURN_PREFER_V6` integration into `/api/system/chat` candidate iteration
  (file as **cbt.7.prefer.integrate** if needed).
- Changing the default to True.
- Probing v6 reachability (connect-then-fallback) — that's a runtime concern
  best handled by cbt.4 failover.

## Implementer

athena → hardener. ETA ~5 min.
