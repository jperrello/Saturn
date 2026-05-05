# CONTRACT — Saturn-cbt.6 / §17.G.2: `routable_addrs()` for multi-interface advertising

**Status:** RED. 3 tests pinned (module does not exist).
**Implementer:** athena will route (recommended: hardener — pure-Python, ~15 LOC + psutil dependency check).

## Spec restatement (falsifiable)

Create `saturn/mdns/interfaces.py` exposing:

```python
def routable_addrs() -> list[str]:
    """All non-loopback, non-link-local IPv4 addresses on UP interfaces."""
```

Implementation per §17.G.2.2: filter `psutil.net_if_addrs()` by
`psutil.net_if_stats()[iface].isup` and `socket.AF_INET`; reject any
address starting with `127.` (loopback) or `169.254.` (link-local).

Add `psutil` to `pyproject.toml` if not already present.

## Test files

- `saturn/tests/test_routable_addrs_cbt6.py` (added; 3 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_routable_addrs_cbt6.py --no-header -rN --tb=short
```

No external dependency beyond `psutil`. Real OS interfaces of the test machine.

## Captured red output

```
saturn/tests/test_routable_addrs_cbt6.py::test_routable_addrs_returns_list_of_ipv4_strings FAILED
saturn/tests/test_routable_addrs_cbt6.py::test_routable_addrs_excludes_loopback_and_link_local FAILED
saturn/tests/test_routable_addrs_cbt6.py::test_routable_addrs_finds_at_least_one_on_typical_host FAILED
========================= 3 failed, 1 warning in 0.06s =========================
```

All three fail with `module saturn/mdns/interfaces.py does not exist`. Full
transcript: `.brutus/Saturn-cbt.6/transcript.md`.

## Oracle definition

| Test | Oracle |
|---|---|
| `returns_list_of_ipv4_strings` | result is `list[str]`; each element parses via `socket.inet_aton` and has 3 dots |
| `excludes_loopback_and_link_local` | no element starts with `"127."` or `"169.254."` |
| `finds_at_least_one_on_typical_host` | `len(result) >= 1` on the dev machine |

## Out of scope

- `UserspaceBackend.advertise()` integration (`addresses=[...]` per §17.G.2.3
  step 1) — file as **cbt.6.userspace**.
- Bonjour / Avahi backends — §17.G.2.3 specifies "no change" for these. They
  already advertise on all interfaces via daemon.
- `SATURN_ADVERTISE_ALL` env opt-out (§17.G.2.5) — file as **cbt.6.optout**
  if desired; default-on covers the spec's intent.
- Multi-NIC integration test (qj5.7 harness with two veth pairs) — needs
  network infrastructure; file as **cbt.6.integration**.

## Implementer

athena will route. Suggested: **hardener**. ETA: 5–10 min (one function +
optionally adding psutil to pyproject).

## Transcript

`.brutus/Saturn-cbt.6/transcript.md`
