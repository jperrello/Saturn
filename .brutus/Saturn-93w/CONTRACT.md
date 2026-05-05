# CONTRACT — Saturn-93w: TOFU pin-race (P1)

**Status:** RED. 3 tests pinned (all error on missing `ALLOWLIST_PATH`).
**Implementer:** athena → hardener (P1, front-of-queue alongside xqw).
**Geoff cite:** `FAILOVER_SECURITY.md` §(A).

## Spec restatement (falsifiable)

`saturn/discovery.py` TOFU has no operator-assertable override. A hostile
peer that registers `<name>` + arbitrary `node_id` BEFORE the legit peer
comes online wins the pin permanently; legit peer is silently filtered to
`rebind_rejected` and disappears from `get_all_services()`. The operator
has no recourse short of hand-editing `~/.saturn/known_nodes.json`.

The fix MUST add an operator-asserted name → node_id allowlist consulted
**before** TOFU promotion / rebind logic:

  - Persistent at `~/.saturn/allowlist.json`. The path MUST be exposed as
    a module-level `pathlib.Path` constant
    `saturn.discovery.ALLOWLIST_PATH` so tests / operators can rebind
    it.
  - Behavior in `_classify_trust(s)` (`saturn/discovery.py:64-75`):
    1. If `s.name` is in the allowlist:
       - `s.node_id == allowlist[s.name]` → return `"allowlist"`.
       - `s.node_id != allowlist[s.name]` → return `"rebind_rejected"`.
       - This branch fires **regardless** of any prior `known_nodes`
         pin state. Allowlist is operator truth.
    2. Otherwise: existing TOFU flow unchanged.

## Test files

- `saturn/tests/test_tofu_pin_race_93w.py` (added; 3 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_tofu_pin_race_93w.py --no-header -rN --tb=short
```

## Captured red

```
3 errors at setup, 1 warning in 0.04s
saturn.discovery must expose `ALLOWLIST_PATH: pathlib.Path` so operators
can preseed name → node_id assertions per geoff's FAILOVER_SECURITY.md
§(A) P1 fix. Today the constant is missing; the operator has no override
path.
```

Transcript: `.brutus/Saturn-93w/transcript.md`.

## Oracle definition

| Test | Setup | Oracle |
|---|---|---|
| `rejects_attacker_node_id` | allowlist `{foo: LEGIT}` | `_classify_trust(foo, ATTACKER) == "rebind_rejected"` |
| `accepts_matching_node_id` | allowlist `{foo: LEGIT}` | `_classify_trust(foo, LEGIT) ∈ {"allowlist", "pinned"}` |
| `overrides_stale_tofu_pin` | known_nodes pin `foo→ATTACKER` + allowlist `{foo: LEGIT}` | `_classify_trust(foo, ATTACKER) == "rebind_rejected"` (NOT `"pinned"`) |

Tests monkeypatch `saturn.discovery.ALLOWLIST_PATH` and
`saturn.mdns.known_nodes.PATH` to a `tmp_path` location so the user's
real `~/.saturn/` is untouched.

## Fix sketch (non-binding)

```python
# saturn/discovery.py — additions near line 27
from pathlib import Path
import json
import threading

ALLOWLIST_PATH = Path.home() / ".saturn" / "allowlist.json"
_allowlist_map: dict[str, str] = {}
_allowlist_lock = threading.Lock()
_allowlist_mtime: float = 0.0


def _load_allowlist():
    global _allowlist_mtime, _allowlist_map
    try:
        st = ALLOWLIST_PATH.stat()
    except (OSError, FileNotFoundError):
        with _allowlist_lock:
            _allowlist_map = {}
            _allowlist_mtime = 0.0
        return
    if st.st_mtime == _allowlist_mtime:
        return
    try:
        data = json.loads(ALLOWLIST_PATH.read_text())
    except (OSError, ValueError):
        return
    if isinstance(data, dict):
        with _allowlist_lock:
            _allowlist_map = {str(k): str(v) for k, v in data.items()}
            _allowlist_mtime = st.st_mtime


def reload_allowlist():
    """Force re-read; used by tests after writing the file."""
    global _allowlist_mtime
    _allowlist_mtime = 0.0
    _load_allowlist()


def _classify_trust(s) -> str:
    _load_allowlist()
    with _allowlist_lock:
        expected = _allowlist_map.get(s.name)
    if expected is not None:
        return "allowlist" if s.node_id == expected else "rebind_rejected"
    # ...existing TOFU logic unchanged...
```

The `_load_allowlist()` call uses an mtime check so the cost is one
`stat()` per classify in the steady state.

## Out of scope

- UI for editing the allowlist. Operator hand-edits the JSON for now.
- Cryptographic name → node_id assertion (signed allowlist, peer-to-peer
  attestation). Future epic.
- Allowlist sync across hosts (cluster-wide truth). File as
  **Saturn-93w.cluster** if multi-host operator workflows surface.
- Auto-promotion of currently-TOFU-pinned entries into the allowlist
  ("learn current state"). Filed as **Saturn-93w.learn** if useful.
- Removing the existing `_allowlist: set` (node_id-only) trust mode
  surface. Geoff's name→node_id map is additional, not a replacement;
  hardener should leave the existing set-mode alone.

## Implementer

athena → hardener. P1, front-of-queue. ETA ~20 min.

## Transcript

`.brutus/Saturn-93w/transcript.md`
