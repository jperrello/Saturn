# CONTRACT: Saturn-8v5 — close server.module auth bypass (re-opens F-1)

Bead: Saturn-8v5 (P1, ship-blocker — same severity as the original 16.1)
Branch: `autonomous/promo-push`
Discovered by: demo (qj5.7 harness regression-pass at c4f9a19)
Related: Saturn-qj5.16.1 (closed at fbb5896 — only the inline ServiceRunner path)

## Spec restatement
qj5.16.1 wired bearer auth into `ServiceRunner.create_app()` (saturn/runner.py:328+). The runner's other branch — `saturn/runner.py:480-487` when `config.server.module` is set — imports the module and uses `mod.app` verbatim, with no auth wrapping. The three built-in server modules (`saturn.servers.ollama`, `saturn.servers.claude`, `saturn.servers.fallback`) all expose `/v1/health`, `/v1/models`, `/v1/chat/completions` unauthenticated. Effect: every default deploy of `saturn run ollama|claude|fallback` exposes the runner /v1 surface to any LAN peer, re-opening F-1.

The fix must produce a single dispatch entry point that uniformly wraps every code path leading to a runtime `/v1/*` app with the same bearer-token dependency used by `ServiceRunner.create_app()`. Required public surface: **`saturn.runner.build_app(config: ServiceConfig) -> FastAPI`**, used by `run_service` for both branches, and importable from tests. The test refuses to hand-roll the dispatch, because that hand-roll is exactly the bug.

Falsifier: any of the 12 assertions failing means the bypass is still reachable.

## Test files
- `saturn/tests/test_server_module_auth.py` (new, 12 tests — 1 inline regression guard + 9 server.module parametrized + 2 bearer-shape)

## Run command
```
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_server_module_auth.py -v
```

## Captured red output (full transcript at `.brutus/8v5/transcript.md`)
```
collected 12 items

12 failed in 0.41s

ALL fail at:
    from saturn.runner import build_app
E   ImportError: cannot import name 'build_app' from 'saturn.runner'

This is the deliberate first red: the dispatch helper does not exist yet. Once
build_app is introduced, the parametrized tests will surface the underlying
bypass on each server.module (ollama / claude / fallback) and on the inline path.
```

## Oracle definition
With `SATURN_RUNNER_TOKEN=<TOKEN>` in env:

1. `from saturn.runner import build_app` succeeds.
2. `build_app(inline_config)` returns an app where `GET /v1/health` without auth → **401** (regression guard for qj5.16.1 — the inline path must keep its auth).
3. For each `module ∈ {saturn.servers.fallback, saturn.servers.ollama, saturn.servers.claude}`, `build_app(ServiceConfig(server=ServerConfig(module=module, port=0), …))` returns an app where:
   - `GET /v1/health` no-auth → 401.
   - `GET /v1/models` no-auth → 401.
   - `POST /v1/chat/completions` no-auth → 401.
4. With the fallback module specifically: wrong bearer → 401; correct bearer → 200 with body `{"saturn": true, ...}`. (Fallback chosen because its `/v1/health` returns 200 unconditionally — no daemon dependency.)

The implementation may wrap the imported app via a `Depends(...)` injected on a router include, an `add_middleware` call, or by mounting the imported app under a guard — any shape that produces 401 on unauth and reaches the original handler on auth is acceptable.

## Out of scope (do NOT touch)
- /api/* admin auth — closed by qj5.16.2 (370f9fa).
- /api/usage* admin gate — closed by qj5.16.10 (3345dbb).
- Default bind host — closed by qj5.16.1.
- F-3 trusted_proxies / X-Forwarded-For allowlist — qj5.16.3, separate bead.
- /api/proxy/{chat,models} body+query keys — qj5.16.6+.7, queued behind this.
- mDNS advertiser changes — keep current behaviour.
- Existing tests under `saturn/tests/` (especially `test_runner_auth.py` qj5.16.1 and `test_web_admin_auth.py` qj5.16.2 and `test_usage_auth.py` qj5.16.10) MUST stay green.

## Acceptance
1. All 12 tests in `saturn/tests/test_server_module_auth.py` go green.
2. `pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py` continues to pass — no regression on shipped P0 contracts.
3. `tests/harness/selftest.py` (demo's harness smoke at c4f9a19) continues to pass — the harness now expects auth on every runner regardless of server.module.
4. `run_service` uses `build_app` as the single source of truth for the runtime app — no two-branch construction left in `run_service` itself.
5. No tokens or auth headers logged — visual on green-phase showboat.

## Implementer
hardener (per athena routing — same pane that landed fbb5896 / 370f9fa / 3345dbb)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/8v5/transcript.md`
