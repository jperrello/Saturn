# CONTRACT — Saturn-x9c / cbt.7.advertise.v6filter: tighten v6 filter in `interfaces.py`

**Status:** RED. 1 test pinned.
**Implementer:** athena → hardener.
**Geoff cite:** security-audit follow-up to Saturn-9rv (cbt.7.advertise).
**Parent:** Saturn-9rv (NOT Saturn-1xh — geoff typo correction).

## Spec restatement (falsifiable)

`saturn/mdns/interfaces.py:24-28` filters out only `::1`, `::`, and
fully-lower / fully-upper `fe80:` link-local. It misses:

  - **ULA**: `fc00::/7` (`fc..`, `fd..`). RFC 4193 unique-local —
    advertising leaks topology and confuses external resolvers.
  - **6to4**: `2002::/16`. Tunneled IPv6-over-IPv4 with unreliable
    reachability; commonly blocked.
  - **Teredo**: `2001::/32`. UDP-tunneled; usually filtered behind NAT.
  - **Mixed-case `fe80`**: e.g., `Fe80::abcd`, `fE80::1`.

The fix MUST exclude every address whose lowercased text starts with one
of those prefixes (`fc`, `fd`, `2002:`, `2001::/32` band, `fe80:`).

## Test files

- `saturn/tests/test_v6_filter_gaps_x9c.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_v6_filter_gaps_x9c.py --no-header -rN --tb=short
```

## Captured red

```
1 failed, 1 warning in 0.06s
v6 filter must exclude ULA (fc/fd), 6to4 (2002::/16), Teredo (2001::/32),
and mixed-case fe80; leaked: ['fc00::1','fd12:3456::1','2002:cb00:7102::1',
'2001::1234','Fe80::abcd']
```

Transcript: `.brutus/Saturn-x9c/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| `routable_addrs(family="v6")` excludes ULA | `fc00::1`, `fd12:3456::1` not in result |
| Excludes 6to4 | `2002:cb00:7102::1` not in result |
| Excludes Teredo | `2001::1234` not in result |
| Excludes mixed-case fe80 | `Fe80::abcd` not in result |
| Keeps legitimate global | `2607:f8b0:4005:809::200e` IS in result |

## Fix sketch (non-binding)

```python
# saturn/mdns/interfaces.py
DISALLOWED_V6_PREFIXES = ("::1", "::", "fe80:", "fc", "fd", "2002:", "2001:")
# ...
elif a.family == socket.AF_INET6 and want_v6:
    bare = ip.split("%", 1)[0].lower()
    if bare in ("::1", "::"):
        continue
    if any(bare.startswith(p) for p in ("fe80:", "fc", "fd", "2002:")):
        continue
    # Teredo: 2001::/32. Match the first 32 bits, not just "2001:" (which
    # also matches the 2001:db8::/32 documentation block; if you want to
    # keep the doc block, gate accordingly).
    if bare.startswith("2001:0:") or bare.startswith("2001::"):
        continue
    out.append(bare)
```

The `2001:` band needs care — `2001:db8::/32` is the documentation block
and may legitimately appear in test fixtures. Implementer should match
the Teredo `2001:0:`/`2001::` first-32-bits rather than the broad
`2001:` prefix.

## Out of scope

- IPv4 link-local / multicast / class-D filter tightening (separate
  family).
- Per-interface allowlist (e.g., only Wi-Fi + Ethernet, skip VPN). That's
  Saturn-zt2 (cbt.5.1.tunnel-leak) — sibling bead.
- Stable-privacy address filtering (RFC 7217). File as
  **Saturn-x9c.privacy** if needed.
- Configurability of the disallow list. File as **Saturn-x9c.config** if
  needed.

## Implementer

athena → hardener. ETA ~10 min.
