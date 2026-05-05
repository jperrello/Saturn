# CONTRACT — Saturn-zd6: bounded `_failover_state` (P1 DoS, geoff's audit headline)

**Status:** RED. 2 tests pinned.
**Implementer:** athena → hardener.
**Priority:** P1 — slot in front of zor / b3o / ggn.

## Spec restatement (falsifiable)

`saturn/web.py:149` is a plain unbounded dict:

```python
_failover_state: dict[str, str] = {}  # conversation_id -> peer_name (sticky)
```

An attacker sending requests with many unique `X-Saturn-Conversation-Id`
values grows the process's resident memory without bound. Geoff scoped
fix: `OrderedDict` + cap + TTL.

Module surface MUST add:

- `MAX_STICKY: int` — module constant, default 10000.
- `STICKY_TTL_S: float` — module constant, default 3600 (1h).
- `_failover_state` MUST be a self-bounding container that:
  1. Caps at `MAX_STICKY` entries (oldest-evicted on overflow).
  2. Treats entries older than `STICKY_TTL_S` as absent (eviction-on-read,
     eviction-on-write, or background sweep — implementer's choice; the
     test accepts any behavior where `key not in dict` OR
     `dict.get(key) is None` after the TTL elapses).

The optional per-IP cap from geoff's scope is **out of scope** here — file
as **Saturn-zd6.per_ip** if/when it lands.

## Test files

- `saturn/tests/test_failover_state_bounded_zd6.py` (added; 2 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_failover_state_bounded_zd6.py --no-header -rN --tb=short
```

## Captured red

```
2 failed, 1 warning in 1.05s
saturn.web must expose `MAX_STICKY` as a module constant ... default 10000.
saturn.web must expose `STICKY_TTL_S` as a module constant (seconds; default 3600) ...
```

Transcript: `.brutus/Saturn-zd6/transcript.md`.

## Oracle definition

| Test | Oracle |
|---|---|
| `caps_at_max_sticky` | after `MAX_STICKY+1` unique-key inserts, `len(_failover_state) <= MAX_STICKY` |
| `evicts_after_ttl` | with `STICKY_TTL_S` monkeypatched to 0.1, key inserted at t=0 is absent (or `.get` returns None) at t≥0.25 |

## Fix sketch (non-binding)

```python
# saturn/web.py
from collections import OrderedDict
import time as _time

MAX_STICKY = 10000
STICKY_TTL_S = 3600.0

class _StickyMap(OrderedDict):
    def __setitem__(self, key, value):
        # purge expired
        cutoff = _time.time() - STICKY_TTL_S
        for k in list(self.keys()):
            if self.get(k, (0, None))[0] < cutoff:
                OrderedDict.__delitem__(self, k)
            else:
                break  # OrderedDict insertion order ≈ time order
        super().__setitem__(key, (_time.time(), value))
        self.move_to_end(key)
        # cap
        while len(self) > MAX_STICKY:
            self.popitem(last=False)

    def __contains__(self, key):
        if not super().__contains__(key):
            return False
        ts, _ = super().__getitem__(key)
        return _time.time() - ts <= STICKY_TTL_S

    def get(self, key, default=None):
        if not super().__contains__(key):
            return default
        ts, value = super().__getitem__(key)
        if _time.time() - ts > STICKY_TTL_S:
            return default
        return value

    def __getitem__(self, key):
        v = self.get(key)
        if v is None:
            raise KeyError(key)
        return v

_failover_state = _StickyMap()
```

The two existing call-sites at line 1110-1111 (`if convo_id and convo_id
in _failover_state: sticky = _failover_state[convo_id]`) and line 1209
(`_failover_state[convo_id] = c["name"]`) work unchanged because the
class implements both `__contains__` and `__getitem__`.

Implementer free to deviate; oracles are what matter.

## Out of scope

- Per-IP cap on sticky entries (geoff listed as optional). → **Saturn-zd6.per_ip**.
- Tightening `MAX_STICKY` default below 10000.
- Distributed sticky map (multi-process). Single-process in-memory is the
  current and correct surface.
- Telemetry on eviction events (count of evictions per period).

## Implementer

athena → hardener. ETA ~15 min.
