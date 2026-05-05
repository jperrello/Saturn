# Saturn-7j3 (qj5.16.13 commit-3) — known-nodes Configure-page UI

*2026-05-05T01:19:47Z by Showboat 0.6.1*
<!-- showboat-id: 8c5d3a43-8db1-4e04-b284-41bdc2ba4664 -->

**Status: scaffold prefetched, awaiting hardener.** Server-side known-nodes admin endpoints (`GET /api/admin/known-nodes`, `POST .../attest`, `POST .../forget`) shipped at 8b1e54d and are 401-gated (qj5.16.13.1+.2 — 44/44 verified). The trust_mode dropdown landed with Saturn-hft. What's outstanding per §15.6 deferred commit-3: the allowlist editor's pick-from-known-nodes affordance and the pending-rejections table with row-level Attest / Forget actions.

## The user-trust angle

TOFU pinning protects against priority-hijack rebinds (F-8) — but only if the admin can *see* what was rejected and intentionally accept (Attest) or drop (Forget) the pin. A pending-rejection that lives only in the server log is invisible. The UI surface makes the policy actionable: prefix-A (expected) vs prefix-B (seen) on the same service name + advertised host, with one-click Attest / Forget.

## Reproducer — 4-surface audit

Spawns saturn web with isolated SATURN_DATA_DIR + SATURN_DEV_MODE=1 (so trust_mode=open is allowed), pre-seeds a pinned known-node via the attest API, then opens `/admin/configure` and audits four surfaces: (a) trust_mode dropdown options, (b) allowlist picker rendering the seeded prefix+name, (c) pending-rejections region, (d) 401-without-bearer regression guards on all three admin endpoints.

```bash
bash demo/recordings/qj5.7j3_probe.sh
```

```output
seed attest: status=200  name=rebind-target-1  prefix=4433213c

(a) trust_mode dropdown: options=['tofu|tofu', 'allowlist|allowlist', 'open|open']
    [X] all three modes present (tofu=True, allowlist=True, open=True)

(b) allowlist picker: regions matching seed_name AND prefix: 0

(c) pending-rejections region: 0

(d) admin endpoints 401 without bearer:
    GET   /api/admin/known-nodes                   401
    POST  /api/admin/known-nodes/attest            401
    POST  /api/admin/known-nodes/forget            401
```

## Reading the matrix today

**Already green (carryover):**

- (a) `#ac-trust_mode` dropdown ships all three modes — `tofu`, `allowlist`, `open` — courtesy of Saturn-hft's schema render.

- (d) `GET /api/admin/known-nodes`, `POST .../attest`, `POST .../forget` all return 401 without an Authorization bearer (qj5.16.13.1+.2).

**Outstanding (gaps Saturn-7j3 closes):**

- (b) **0 regions** match BOTH the seeded `service` name AND the seeded `node_id` prefix (first 8 chars). Today there's no surface that fetches `GET /api/admin/known-nodes` and lets the admin click-to-add into `trusted_node_ids`. The bare `#ac-trusted_node_ids` text input from Saturn-hft is the only way to populate the allowlist; admins must paste UUIDs by hand.

- (c) **0 regions** carry a `pending rejections` / `rebind rejected` heading. Even with the empty-rejected-list case, the container itself doesn't render. When a rebind hits the policy, today the only signal is a server log line.

## What the post-fix matrix should look like

    (a) trust_mode dropdown    [X] tofu  [X] allowlist  [X] open

    (b) allowlist picker       regions matching seed_name AND prefix: ≥ 1

                               (list / table / datalist / dropdown / popover all OK)

    (c) pending-rejections     ≥ 1 region; populated case shows

                               'rebind-target' + 22222222 + 33333333 +

                               two visible buttons matching

                               /attest|trust|accept/i and /forget|reject|delete|remove/i

    (d) admin endpoints 401    GET, POST attest, POST forget all 401 (already green)

## Verifying drift

    bash demo/recordings/qj5.7j3_probe.sh

    uvx showboat verify demo/recordings/qj5.7j3-known-nodes-ui.md  # diff

Once the UI lands, expect (b) hits ≥ 1 and (c) regions ≥ 1; capture an after-state screenshot via `LABEL=after PYTHONPATH=. python3 demo/recordings/_capture_qj5_7j3.py` and attach with `uvx showboat image`.

## Implementation pointers

- Markup: extend `Web-UI/index.html` `#admin-configure-page` with a Service-Identity sub-region carrying the picker (next to `#ac-trusted_node_ids`) and a sibling `fieldset` for pending rejections.

- Wiring: `Web-UI/app.js` calls `fetch('/api/admin/known-nodes')` (the harness already injects Authorization Bearer on /api/* via add_init_script + extra_http_headers); render the `pinned` list as a click-to-add and the `rejected` list as the table. Attest button → `POST .../attest {service, node_id: <seen>}`; Forget button → `POST .../forget {service}`.

- Test surface: `saturn/tests/test_known_nodes_ui.py` (6 tests; 3 RED + 3 PASS today as regression guards).

- Probe note: the seeded prefix is the first 8 chars of `node_id` with hyphens stripped — same shape the contract test asserts. Force `SATURN_DEV_MODE=1` if the seeded `trust_mode=open` is needed to skip the validator gate.
