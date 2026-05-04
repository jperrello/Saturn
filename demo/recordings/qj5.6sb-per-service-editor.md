# Saturn-6sb (qj5.13 commit-3) — per-service editor on the Configure page

*2026-05-04T22:34:17Z by Showboat 0.6.1*
<!-- showboat-id: 358590df-c32b-4fc9-ac2c-0dd88f333ff8 -->

**Status: scaffold prefetched, awaiting hardener (queues after Saturn-hft).** Per-service CRUD (list / create / edit / delete) lives on the admin Configure view as one of its eight group sections (or a sibling), surfacing CONFIG_FIELDS §B fields against the existing /api/services API. Five falsifiable surfaces: (a) section lists existing services, (b) UI Create round-trips through POST /api/services, (c) UI Edit propagates without restart, (d) UI Delete confirms then DELETEs, (e) sensitive auth surface gated — `api_key_env` / "env var name" — never plaintext.

## The user-trust angle (especially (e))

Saturn's invariant from `saturn/web.py:1213` is **the value of an api key never traverses a request body** — configs hold the *name* of an env var. The UI must reflect that. A plaintext `api_key` input on the editor would violate the invariant on the wire and in the DOM. The probe today flags it directly.

## Reproducer — admin probe with token-injected fetch + service seed

Spawns saturn web with isolated SATURN_DATA_DIR + SATURN_SERVICES_DIR + SATURN_DEV_MODE=1; injects the admin bearer into sessionStorage and patches window.fetch on /api/* calls; seeds two services via POST /api/services; navigates the candidate admin paths; reports which sections look like the editor, lists any plaintext api-key inputs, and surfaces which CONFIG_FIELDS §B fields are present.

```bash
bash demo/recordings/qj5.6sb_probe.sh
```

```output
seed seed-alpha: 200
seed seed-bravo: 200
resolved url: http://127.0.0.1:54792/admin/configure
per-service editor regions found: 0
plaintext api-key inputs (must be 0): 1
  LEAK: <input type="password" id="cfg-api-key" placeholder="sk-..." style="">
  [ ] surfaces: max_budget_usd
  [ ] surfaces: allowed_models
  [ ] surfaces: require_https
  [ ] surfaces: require_runner_token
  [ ] surfaces: api_key_env

GET /api/services: 8 entries; seeded names present: ['seed-alpha', 'seed-bravo']
```

## Reading the output today

Two seeds POST cleanly (status 200) and GET /api/services returns 8 entries including both seeded names — server-side CRUD is ready. The UI side reads RED across the board:

- 0 per-service editor regions match the contract heuristic.

- **One plaintext api-key input is currently leaking** (`<input type="password" id="cfg-api-key" placeholder="sk-...">`). Saturn-6sb (e) requires this to either disappear or be relabeled `api_key_env` — env-var name, not the value.

- None of the §B.2/B.3/B.4 fields (`max_budget_usd`, `allowed_models`, `require_https`, `require_runner_token`, `api_key_env`) surface yet.

**That is the gap Saturn-6sb closes.**

## When commit lands — one-step refresh

    bash demo/recordings/qj5.6sb_probe.sh

    LABEL=after PYTHONPATH=. python3 demo/recordings/_capture_qj5_6sb.py

    uvx showboat verify demo/recordings/qj5.6sb-per-service-editor.md  # diff

Once the editor lands, expect: ≥ 1 editor region whose innerText contains both seeded names; `plaintext api-key inputs (must be 0): 0`; ≥ 1 §B-section field surfacing; the full-page screenshot at `demo/recordings/qj5.6sb-after-fullpage.png` shows the editor with the seeded rows.

## Implementation pointers

- Existing CRUD: `saturn/web.py` /api/services (GET/POST/PATCH/DELETE) — already authed via require_admin + bearer token.

- Test surface: `saturn/tests/test_per_service_editor.py` (5 tests, all RED today).

- Editor lives inside the admin Configure view from Saturn-hft (commit-2); landing order is hft → 6sb.

- Drop the legacy `#cfg-api-key` plaintext input or rename to `#cfg-api-key-env` per §B.5; this scaffold's probe will flip the LEAK line to `plaintext api-key inputs (must be 0): 0`.
