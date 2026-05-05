# CONTRACT — Saturn-cbt.5 / §17.G.1: AP isolation detection probe

**Status:** RED. 2 tests pinned (module does not exist).
**Implementer:** athena will route (recommended: hardener — new module + Zeroconf round-trip).

## Spec restatement (falsifiable)

Create `saturn/mdns/isolation.py` exposing:

```python
@dataclass
class IsolationProbe:
    advertising: bool
    self_seen: bool
    peers_seen: int
    ifaces_with_link: List[str]
    suspected_ap_isolation: bool
    diagnosis: str

def probe(timeout: float = 4.0) -> IsolationProbe: ...
```

`probe()` MUST advertise a transient `_saturn-probe._tcp.local.` record on a
random port and browse for it from the same process. On a normal
loopback / LAN, the result MUST satisfy:

- `advertising == True`
- `self_seen == True`
- `suspected_ap_isolation == False`

The diagnosis-classification logic (§17.G.1.2: which combinations indicate
AP isolation vs no network vs broken loopback) is exercised only at the
"loopback healthy" boundary by this contract — adversarial network states
require infrastructure (`pfctl`, guest hotspots) and are filed as
**cbt.5.adversarial** sub-bead.

## Test files

- `saturn/tests/test_isolation_cbt5.py` (added; 2 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_isolation_cbt5.py --no-header -rN --tb=short
```

No external dependency (loopback only).

## Captured red output

```
saturn/tests/test_isolation_cbt5.py:35: Failed: module saturn/mdns/isolation.py
  does not exist. Create it per PRE_SPECS_B3.md §17.G.1.2 with: IsolationProbe
  dataclass (advertising, self_seen, peers_seen, ifaces_with_link,
  suspected_ap_isolation, diagnosis), and probe(timeout=4.0) -> IsolationProbe.
========================= 2 failed, 1 warning in 0.07s =========================
```

Full transcript: `.brutus/Saturn-cbt.5/transcript.md`.

## Oracle definition

| Test | Oracle |
|---|---|
| `module_surface` | module exposes `probe`, `IsolationProbe`; `IsolationProbe` is a `@dataclass`; all 6 fields present |
| `loopback_probe_self_seen_is_true` | `result.advertising == True`; `result.self_seen == True`; `result.suspected_ap_isolation == False`; returned object is an `IsolationProbe` instance |

## Out of scope

- Adversarial network states (real AP isolation, no-link, firewall) — file
  as **cbt.5.adversarial** when isolation.py lands.
- `/api/discover` integration (response gains `isolation` key per §17.G.1.3)
  — file as **cbt.5.web**.
- Web-UI Network Scan empty-state copy (§17.G.1.4) — UI lane (route to
  bombadil/forge).
- Probe failure / timeout fallback diagnosis text (§17.G.1.7) — fold into
  cbt.5.adversarial.

## Implementer

athena will route. Suggested: **hardener**. ETA: 20–30 min (Zeroconf publish +
browse round-trip in same process; see `saturn/tests/test_discovery.py` for
the test-side pattern).

## Transcript

`.brutus/Saturn-cbt.5/transcript.md`
