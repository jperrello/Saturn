# CONTRACT — Saturn-cbt.7 / §17.G.3: dual-stack address-plural schema

**Status:** RED. 3 tests pinned.
**Implementer:** athena will route (recommended: hardener — small dataclass extensions; resolve plumbing is a separate sub-bead).

## Spec restatement (falsifiable)

`ServiceRecord` (`saturn/mdns/backend.py:6-12`) and `SaturnService`
(`saturn/discovery.py:75-95`) MUST gain address-plural fields per
§17.G.3.2:

```python
# saturn/mdns/backend.py
@dataclass
class ServiceRecord:
    name: str
    node_id: str
    host: str
    port: int
    txt: dict[str, str]
    addresses: list[str] = field(default_factory=list)   # NEW (must be last for back-compat positional)

# saturn/discovery.py
@dataclass
class SaturnService:
    ...
    addresses: list[str] = field(default_factory=list)   # NEW
    ipv6: Optional[str] = None                            # NEW
```

`addresses` carries every resolved A and AAAA address (textual form). `ipv6`
is a convenience pointing at the first AAAA if any.

This contract pins the schema-level surface only. Per-backend resolve
plumbing (userspace `info.addresses` walk for v4/v6, Bonjour
`DNSServiceGetAddrInfo`, Avahi protocol-specific browse) is the larger
implementation surface and is filed as **cbt.7.resolve** sub-bead.

## Test files

- `saturn/tests/test_dual_stack_cbt7.py` (added; 3 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_dual_stack_cbt7.py --no-header -rN --tb=short
```

No external dependency.

## Captured red output

```
saturn/tests/test_dual_stack_cbt7.py FFF                                 [100%]
saturn/tests/test_dual_stack_cbt7.py:65: TypeError:
  ServiceRecord.__init__() got an unexpected keyword argument 'addresses'
========================= 3 failed, 1 warning in 0.12s =========================
```

Full transcript: `.brutus/Saturn-cbt.7/transcript.md`.

## Oracle definition

| Test | Oracle |
|---|---|
| `servicerecord_has_addresses_list_field` | `dataclasses.fields(ServiceRecord)` includes `addresses`; default = `[]` |
| `saturnservice_has_addresses_and_ipv6_fields` | `SaturnService` has both `addresses` (default `[]`) and `ipv6` (default `None`) |
| `servicerecord_addresses_accepts_dual_stack_strings` | constructing with `addresses=["192.168.1.10","fe80::1"]` retains both |

## Out of scope

- Per-backend resolve plumbing (userspace `info.addresses` walk for v4/v6,
  Bonjour `DNSServiceGetAddrInfo`, Avahi protocol-specific browse). →
  **cbt.7.resolve**.
- Advertise-side `routable_addrs` extension to v6 (§17.G.3.3 last paragraph).
  → **cbt.7.advertise**.
- `SATURN_PREFER_V6` env handling (§17.G.3.5). → **cbt.7.prefer**.
- Web-UI IPv6 badge (§17.G.3.4). → UI lane.
- Dedup of dual-stack-same-node_id entries in `SaturnDiscovery._on_event`
  (§17.G.3.6 second test). → **cbt.7.dedup**.
- Any change to `host` (back-compat primary); existing callers using
  `service.host` MUST keep working unchanged.

## Implementer

athena will route. Suggested: **hardener**. ETA: 5 min (two `field(...)` lines
plus `Optional[str] = None`).

## Transcript

`.brutus/Saturn-cbt.7/transcript.md`
