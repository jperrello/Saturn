# CONTRACT — Saturn-1xh / cbt.7.resolve (= geoff's cbt.7.1): userspace dual-stack address extraction

**Status:** RED. 1 test pinned.
**Implementer:** athena → hardener.
**Geoff cite:** `PARITY_REVIEW_MAY05.md` §(b) B-2 + §(c) Saturn-cbt.7.1.

## Spec restatement (falsifiable)

`saturn/mdns/userspace.py:28-47`'s `_resolve()` currently extracts only
`info.addresses[0]` via `socket.inet_ntoa` (4-byte / IPv4 only). Per
§17.G.3.3, the returned `ServiceRecord.addresses` MUST contain every
advertised address in textual form, dispatching by length:

```python
addrs = []
for addr in (info.addresses or []):
    if len(addr) == 4:
        addrs.append(socket.inet_ntoa(addr))
    elif len(addr) == 16:
        addrs.append(socket.inet_ntop(socket.AF_INET6, addr))
host = addrs[0] if addrs else (info.server.rstrip(".") if info.server else "unknown")
return ServiceRecord(..., host=host, addresses=addrs, ...)
```

The back-compat `host` field continues to point at the first address.

This contract pins the **userspace** path only. Bonjour
(`saturn/mdns/bonjour.py:359-398` + `DNSServiceGetAddrInfo`) and Avahi
(`saturn/mdns/avahi.py:207-224` + dual-protocol callbacks) are separate
sub-beads — file as **cbt.7.resolve.bonjour** / **cbt.7.resolve.avahi**.

## Test files

- `saturn/tests/test_dual_stack_resolve_cbt7_resolve.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_dual_stack_resolve_cbt7_resolve.py --no-header -rN --tb=short
```

## Captured red

```
1 failed, 1 warning in 2.39s
v6 address must be present in textual form via inet_ntop(AF_INET6, ...);
got addresses=[]
```

Transcript: `.brutus/Saturn-1xh/transcript.md`.

## Oracle

| Field | Oracle |
|---|---|
| `rec.addresses` | non-empty, list of strings |
| `"127.0.0.1"` in `rec.addresses` | True |
| At least one entry contains `:` and decodes as the v6 we registered | True |

## Out of scope

- Bonjour resolve plumbing (`DNSServiceGetAddrInfo` chain) — **cbt.7.resolve.bonjour**.
- Avahi protocol-specific accumulation — **cbt.7.resolve.avahi**.
- Discovery dedup of dual-stack same-node_id — **Saturn-7sg / cbt.7.dedup**.
- Advertise-side AAAA — **Saturn-9rv / cbt.7.advertise**.
- Selecting v6 over v4 at connect time — **Saturn-76f / cbt.7.prefer**
  (already contracted).

## Implementer

athena → hardener. ETA ~15 min.
