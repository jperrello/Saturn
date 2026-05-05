# CONTRACT — Saturn-cbt.3.b: userspace parallel resolves

**Status:** RED. 1 test pinned.
**Implementer:** athena will route (recommended: hardener — small `ThreadPoolExecutor` wrap in `userspace.py`).

## Spec restatement (falsifiable)

`saturn/mdns/userspace._Listener.add_service` (line 55) and `update_service`
(line 60) call `_resolve()` synchronously from zeroconf's listener thread.
Multiple concurrent service adds therefore serialize on a single thread; under
bursty advertisement, the `Zeroconf.get_service_info()` (default 3s) timeouts
stack up.

The fix MUST guarantee that when 12 services are advertised in quick
succession, the resulting `'added'` callbacks fire from **at least 2 distinct
OS threads**. The cleanest implementation is a `ThreadPoolExecutor(max_workers=8)`
that runs `_resolve` and dispatches the callback off the listener thread.

## Test files

- `saturn/tests/test_userspace_parallel_resolve_cbt3b.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_userspace_parallel_resolve_cbt3b.py --no-header -rN --tb=short
```

No external dependency — Zeroconf advertisers on loopback.

## Captured red output

```
saturn/tests/test_userspace_parallel_resolve_cbt3b.py:95: AssertionError:
  add_service callbacks fired from only 1 thread(s) (idents=[6184398848]).
  _resolve() blocks the zeroconf engine thread; dispatch resolves to a
  ThreadPoolExecutor at saturn/mdns/userspace.py:55-63 so concurrent adds run
  in parallel. Saw 12 adds total.
======================== 1 failed, 1 warning in 20.21s =========================
```

Full transcript: `.brutus/Saturn-cbt.3.b/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| All 8+ adds arrive within 15s | `received.wait(timeout=15.0) == True` |
| Distinct callback thread idents | `len(set(seen_threads)) >= 2` |

## Fix sketch (non-binding)

In `saturn/mdns/userspace.py`:

```python
from concurrent.futures import ThreadPoolExecutor

class _Listener(ServiceListener):
    def __init__(self, zc, callback):
        self._zc = zc
        self._cb = callback
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="saturn-resolve")
        self._inflight: set[str] = set()
        self._lock = threading.Lock()

    def _dispatch(self, action, type_, name):
        with self._lock:
            if name in self._inflight:
                return
            self._inflight.add(name)
        def _do():
            try:
                rec = _resolve(self._zc, type_, name) if action != "removed" else ServiceRecord(...)
                if rec:
                    self._cb((action, rec))
            finally:
                with self._lock:
                    self._inflight.discard(name)
        self._pool.submit(_do)

    def add_service(self, zc, type_, name): self._dispatch("added", type_, name)
    def update_service(self, zc, type_, name): self._dispatch("updated", type_, name)
    def remove_service(self, zc, type_, name): self._dispatch("removed", type_, name)
```

Implementer is free to use any approach (executor, raw threads with semaphore,
asyncio task) that satisfies the oracle. Cap fan-out per audit's note 2.

## Out of scope

- Bonjour backend's unbounded thread fan-out (audit suggests
  `BoundedSemaphore(16)` at `saturn/mdns/bonjour.py:329-333`). File as
  cbt.3.b.bonjour if needed — separate platform path.
- The 50-service / 8s timeout invariant from the audit — that test is hard
  to make non-flaky on shared CI hardware. The thread-count oracle here is
  more deterministic and proves the same architectural property.
- `socket.gethostbyname` resolves at advertiser startup
  (`saturn/discovery.py:420`) — only on the publish path, not the discovery
  hot path.

## Implementer

athena will route. Suggested: **hardener**. ETA: 15–20 min (executor wrap
plus dedupe for in-flight resolves).

## Transcript

`.brutus/Saturn-cbt.3.b/transcript.md`
