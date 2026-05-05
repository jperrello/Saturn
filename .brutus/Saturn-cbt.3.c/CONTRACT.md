# CONTRACT — Saturn-cbt.3.c: known_nodes.json cross-process safety

**Status:** RED. 1 test pinned. Behavior is missing.
**Implementer:** athena will route (recommended: hardener — wrap `save()` with `fcntl.flock`).

## Spec restatement (falsifiable)

`saturn/mdns/known_nodes.py` currently serializes `pin()` / `record_rejection()`
/ `attest()` only via a process-local `threading.Lock` (line 17). When two
Saturn instances on the same host write concurrently, they race on the
`.tmp → os.replace` shuffle in `save()` (line 52-57), producing either a
subprocess crash (`FileNotFoundError` on `os.chmod` or `os.replace`) or
silently-lost entries.

The fix MUST guarantee that 2 processes each calling `pin(name_i, node_id_i, host)`
N times in parallel produce a final `~/.saturn/known_nodes.json` whose `nodes`
dict contains all 2N entries, with no subprocess crash and no JSON parse
failure.

## Test files

- `saturn/tests/test_known_nodes_cross_proc_cbt3c.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_known_nodes_cross_proc_cbt3c.py --no-header -rN --tb=short
```

Test redirects `$HOME` for the children — the user's actual
`~/.saturn/known_nodes.json` is not touched.

## Captured red output

```
saturn/tests/test_known_nodes_cross_proc_cbt3c.py:89: AssertionError:
  cross-process pin race detected.
  subprocess failures=[('b', 1, "...FileNotFoundError: ...known_nodes.tmp...")];
  missing entries: 100 of 200 (e.g. ['a-013', 'b-001', 'b-002', ...]).
  Both symptoms point at the same root: saturn/mdns/known_nodes.py serializes
  load→save only with threading.Lock, not fcntl.flock.
========================= 1 failed, 1 warning in 0.48s =========================
```

Full transcript: `.brutus/Saturn-cbt.3.c/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| Both subprocesses exit 0 | `failures == []` |
| `known_nodes.json` parses cleanly | no `ValueError` from `json.loads` |
| All 2N entries present | `expected - set(nodes.keys()) == set()` |

Test parameters: 2 subprocesses, N=100 each, distinct names per child.

## Fix sketch (non-binding)

In `saturn/mdns/known_nodes.py`, wrap the `save()` body — or the entire
load+modify+save cycle inside each mutator — with `fcntl.flock(LOCK_EX)` on a
sibling `.lock` file (don't lock the JSON itself; the rename invalidates that
fd). Sketch:

```python
import fcntl, contextlib

LOCK_PATH = PATH.with_suffix(".lock")

@contextlib.contextmanager
def _flock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    f = open(LOCK_PATH, "a+")
    fcntl.flock(f, fcntl.LOCK_EX)
    try: yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
```

Then each mutator:

```python
def pin(...):
    with _lock, _flock():
        state = load()
        ...
        save(state)
```

Implementer is free to use any approach (POSIX flock / per-platform / different
sentinel) that satisfies the oracle.

## Out of scope

- Windows portability (saturn is macOS / Linux today; `fcntl` is fine).
- The bounded `rejected` list — DISCOVERY_AUDIT.md flagged it as unbounded
  but the code already trims at `MAX_REJECTED=50` (`known_nodes.py:107`).
  No fix needed; brutus does not pin a regression test for this.
- Any other audit area (a/b/d are separate brutus contracts).
- Migration of existing `known_nodes.json` files.

## Implementer

athena will route. Suggested: **hardener**. ETA: 5–10 min (small wrap, plus
running the test to confirm green).

## Transcript

`.brutus/Saturn-cbt.3.c/transcript.md`
