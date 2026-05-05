# Fake-MCP-server scaffolding sketch

Research note for unblocking **Saturn-ex3** (cbt.2.c.timeout) and
**Saturn-eic** (cbt.2.c.large). Not a contract yet — sketch only.

## (a) Reuse the MCP SDK we already depend on

The project already imports `mcp` (`saturn/mcp_client.py:6-7`). The same
package ships `mcp.server.FastMCP`, which speaks streamable HTTP — exactly
the transport our client uses.

```python
from mcp.server import FastMCP   # already in deps

m = FastMCP("brutus-fake", host="127.0.0.1", port=PORT,
            stateless_http=True)         # avoids per-session SQLite stuff

@m.tool()
def hang(seconds: float) -> str:
    import time; time.sleep(seconds)
    return "done"

@m.tool()
def bigblob(megabytes: int) -> str:
    return "x" * (megabytes * 1024 * 1024)

m.run(transport="streamable-http")
```

`m.streamable_http_app()` also returns a bare ASGI app if we want to mount
ourselves on uvicorn directly (needed for in-process; not for subprocess).

**No new dependency.** Pure reuse.

## (b) In-test fixture shape — subprocess wins

Three options considered; pick **subprocess**:

| Shape | Pros | Cons | Verdict |
|---|---|---|---|
| **Subprocess** (spawn `python fake_mcp.py`, kill in teardown) | Isolation; matches cbt.4 peer pattern; can SIGKILL mid-session to exercise unreachable; no event-loop entanglement | Slower fixture startup (~1s wait_up) | **Pick.** Mirrors what we already do. |
| **Threaded uvicorn** in pytest's loop | No subprocess overhead | uvicorn + pytest event loop fights; killing is messy; can't simulate hard crash | Skip. |
| **In-process ASGI direct** (call ASGI app via httpx) | Fastest | bypasses `streamablehttp_client` entirely; doesn't actually exercise the wire | Skip — defeats the whole point. |

Sketch (drop-in):

```python
# saturn/tests/_fixtures/fake_mcp.py — module written into tmp_path then
# spawned. Mirrors the PEER_SRC pattern in test_failover_cbt4.py.
FAKE_MCP_SRC = r'''
import os, sys, time
from mcp.server import FastMCP

PORT = int(os.environ["FAKE_MCP_PORT"])
HANG_SECONDS = float(os.environ.get("FAKE_MCP_HANG", "0"))
BLOB_MB      = int(os.environ.get("FAKE_MCP_BLOB_MB", "0"))

m = FastMCP("brutus-fake", host="127.0.0.1", port=PORT, stateless_http=True)

@m.tool()
def echo(text: str) -> str:
    if HANG_SECONDS > 0:
        time.sleep(HANG_SECONDS)
    if BLOB_MB > 0:
        return "x" * (BLOB_MB * 1024 * 1024)
    return text

if __name__ == "__main__":
    m.run(transport="streamable-http")
'''
```

```python
# in test file, fixture
@pytest.fixture
def fake_mcp(tmp_path, monkeypatch):
    src = tmp_path / "fake_mcp.py"
    src.write_text(FAKE_MCP_SRC)
    port = _free()
    env = {**os.environ, "FAKE_MCP_PORT": str(port)}
    # add per-test overrides via monkeypatch.setenv before this fixture runs
    proc = subprocess.Popen([sys.executable, str(src)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}/mcp"
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base, timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    try:
        yield {"url": base, "proc": proc, "port": port}
    finally:
        try: proc.terminate()
        except Exception: pass
        try: proc.wait(timeout=3)
        except Exception: proc.kill()
```

Per-test config via `monkeypatch.setenv("FAKE_MCP_HANG", "30")` BEFORE
constructing the fixture.

A tiny wrinkle: the streamable-http endpoint path is `/mcp` by default
(see `streamable_http_path` in `FastMCP.__init__`). The wait-up probe
should poke it (any HTTP method; 405/406 still proves the server is up).

## (c) Where it slots beside `test_mcp_edges_cbt2c.py`

Two new sibling files, NOT additions to the existing one:

- `saturn/tests/test_mcp_edges_timeout_cbt2c_timeout.py` — **Saturn-ex3**.
  Uses `fake_mcp` with `FAKE_MCP_HANG=30` (or whatever > target client
  timeout). Calls `MCPClientManager.call("fake", "echo", {"text":"hi"})`,
  asserts it returns within ~5s with an error mentioning "timeout".
  Currently `mcp_client.call` would block ~5 minutes on `sse_read_timeout`
  default 300s — clear red.

- `saturn/tests/test_mcp_edges_large_cbt2c_large.py` — **Saturn-eic**.
  Uses `fake_mcp` with `FAKE_MCP_BLOB_MB=10`. Calls `MCPClientManager.call`
  for the `echo` tool, asserts the response is either truncated with a
  marker (e.g., a `truncated=True` flag in the dict) OR raises a
  `TooLarge`-style error. Today the client will happily buffer the whole
  10MB into memory — a falsifiable "needs a guard" red.

The fixture itself lives in `saturn/tests/_fixtures/fake_mcp.py` (new
module) — both new tests import it. The existing
`test_mcp_edges_cbt2c.py` (unreachable case) keeps the closed-port trick
and does NOT need the fake server. Three orthogonal MCP-edge files, one
shared fixture for the two that need a live peer.

## Caveats / things to confirm before writing the contracts

1. **Default `streamable_http_path`** is `/mcp` per FastMCP source — the
   client URL must be `http://host:port/mcp`, not `http://host:port/`.
   Verify by spinning a fixture in a scratch script before the contract
   runs, or the test gets a confusing 404.

2. **`stateless_http=True`** dodges the SSE-resumability event store
   requirement. We don't need cross-call state.

3. **MCP `call_tool` happens inside an `asyncio` server loop.** A blocking
   `time.sleep` in the tool body will block the event loop and starve other
   requests in the same process. For our tests this is fine (one client,
   one tool), but a future test that needs *concurrent* in-flight calls
   would need `await asyncio.sleep`.

4. **Client-side timeout configuration in `saturn/mcp_client.py`:** the
   wrapper passes `timeout=30, sse_read_timeout=300` defaults from
   `streamablehttp_client`. The Saturn-ex3 implementation will likely tighten
   `sse_read_timeout` — the test should pin a *call-level* deadline (e.g.,
   `asyncio.wait_for(mgr.call(...), timeout=5)` proxy assertion via
   wall-clock measurement) rather than over-couple to which knob the
   implementer turns.

5. **Oversized payload threshold** is a policy choice. Suggested oracle:
   the client refuses anything beyond e.g. 1 MiB; the test sends a 10 MiB
   blob and asserts either truncation OR an error. Let geoff or Joey
   pick the exact ceiling at contract-write time; brutus will pin the
   discriminating case.

## Hand-off

When hardener queue clears: convert this sketch into two contracts
(Saturn-ex3 and Saturn-eic), both reading from the shared fixture.
Estimated authoring time per contract: ~15 min, mostly drafting oracle text.
