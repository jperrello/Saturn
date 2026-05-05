# CONTRACT: Saturn-qj5.16.6 + qj5.16.7 — combined (proxy body/query key removal)

Beads: Saturn-qj5.16.6 (F-5, P1) + Saturn-qj5.16.7 (F-6, P1) — co-landable per SECURITY_AUDIT §12.5
Branch: `autonomous/promo-push`
Spec source: `SECURITY_AUDIT.md` §11 + §12 + `CONFIG_FIELDS.md` §A.6 (proxy hygiene).

## Spec restatement

`saturn/web.py` exposes two proxy routes that accept caller-supplied API keys via insecure transports:

- **F-5** `/api/proxy/chat` accepts `api_key` as a JSON body field on `ManualChatRequest` (`saturn/web.py:758-766`). The handler at `:783-784` lifts that key into `Authorization: Bearer ...` for the upstream. No internal caller populates the field today (Web-UI/app.js sends only `{base_url, model, messages, api_type, ...params}`); it is dormant capability that invites hand-crafted callers to paste real keys into request bodies. Compounding this, `:794-796` echoes upstream error bodies verbatim back into the SSE stream — a small reflected-content surface.
- **F-6** `/api/proxy/models` accepts `api_key` as a Query parameter (`:726-727`). Query-string secrets leak across access logs, browser history, `Referer` headers, reverse-proxy logs, error trackers, and copy-pasted URLs (audit §12.3 matrix). Same dormant-capability story.

The combined fix:

1. Delete `api_key` from `ManualChatRequest` and add `model_config = ConfigDict(extra="forbid")` so a body that still carries `api_key` returns 422.
2. Drop the `api_key: str = Query(default="")` parameter from `/api/proxy/models`; tighten the signature so a query that still carries `api_key=...` returns 422.
3. In both handlers, read inbound `Authorization: Bearer ...` from the request headers and forward it verbatim to the upstream.
4. Sanitise the upstream-failure surface in both handlers — no upstream body, URL, or exception text leaks back into the response.

Falsifier: any of the six assertions below failing means the implementation still has a key-bearing channel or a leak surface.

## Test files
- `saturn/tests/test_proxy_no_body_keys.py` (new, 6 tests, real local http upstream — no mocks)

## Run command
```
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_proxy_no_body_keys.py -v
```

## Captured red output (full transcript at `.brutus/qj5.16.6-7/transcript.md`)
```
collected 6 items

6 failed in 4.11s

FAILED test_proxy_chat_rejects_body_api_key                          (body api_key currently accepted, expects 422)
FAILED test_proxy_chat_passthrough_authorization_header               (inbound Authorization not forwarded to upstream)
FAILED test_proxy_chat_does_not_echo_upstream_error_body              (verbatim upstream body still reflected into SSE)
FAILED test_proxy_models_rejects_query_api_key                        (api_key Query still accepted, expects 422)
FAILED test_proxy_models_passthrough_authorization_header             (inbound Authorization not forwarded to upstream)
FAILED test_proxy_models_502_does_not_leak_upstream_details           (502 body leaks upstream URL + exception text)
```

## Oracle definition

Fixture: env-bootstrapped `saturn.web` reload (admin token, password, data dir, rate-limit envs raised so the chat route is not throttled). A real `http.server.ThreadingHTTPServer` runs on `127.0.0.1:<random>` as the upstream; the fixture records every inbound request's headers in a list and lets the test mutate `state["status"]` and `state["body"]`.

### F-5 — `/api/proxy/chat`

1. **`test_proxy_chat_rejects_body_api_key`** — `POST /api/proxy/chat` with body `{"base_url", "model", "messages", "api_key": "sk-…"}` returns **422**. Pydantic must reject the unknown `api_key` field via `extra="forbid"`.
2. **`test_proxy_chat_passthrough_authorization_header`** — `POST /api/proxy/chat` with header `Authorization: Bearer <T>` and a body that contains NO `api_key` results in the upstream receiving `Authorization: Bearer <T>` verbatim.
3. **`test_proxy_chat_does_not_echo_upstream_error_body`** — When the upstream returns 401 with body `{"error": "leaked upstream secret echo Bearer ******abc"}`, the response from `/api/proxy/chat` (the SSE stream as captured by `r.text`) contains neither the `leaked upstream secret echo` substring nor the `******abc` substring.

### F-6 — `/api/proxy/models`

4. **`test_proxy_models_rejects_query_api_key`** — `GET /api/proxy/models?base_url=…&api_key=sk-…` returns **422**.
5. **`test_proxy_models_passthrough_authorization_header`** — `GET /api/proxy/models?base_url=…` with `Authorization: Bearer <T>` results in the upstream receiving `Authorization: Bearer <T>`.
6. **`test_proxy_models_502_does_not_leak_upstream_details`** — When the upstream returns 401 with body `{"error": "secret-fragment-xyz"}`, `/api/proxy/models` returns 502 whose body contains neither the upstream URL nor the substring `secret-fragment-xyz`.

## Out of scope (do NOT touch)
- Adding the runner-token gate to `/api/proxy/chat` and `/api/proxy/models`. Per CONFIG_FIELDS §A.5 these belong to the runner-token group, not the admin-token group landed in qj5.16.2. Auth-gating these is a *separate* bead; this contract only closes the body/query-key channels and the leak surfaces.
- `/api/chat`, `/api/models`, `/api/proxy/models` POST alias proposed in audit §12.4 — out of scope; pure deletion / sanitisation only.
- The `data/admin_config.json` `redact_proxy_keys_in_logs` switch (CONFIG_FIELDS §A.6) — separate config-page bead.
- `Web-UI/app.js` — no UI change required; the manual-endpoint flow already sends no `api_key`.
- Existing 16.1 / 16.2 / 16.10 / 8v5 auth suites — must stay green. The proxy-chat fixture explicitly does **not** set the admin token on its outbound requests, because `/api/proxy/chat` is not yet admin-gated and adding that is out of scope for this bead.

## Acceptance
1. All 6 tests in `saturn/tests/test_proxy_no_body_keys.py` go green.
2. `pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py` continues to pass — no regression on shipped P0/P1 contracts.
3. `tests/harness/selftest.py` continues to pass.
4. The `ManualChatRequest` model_config explicitly sets `extra="forbid"` (review item, not directly asserted; the 422 assertion is the user-visible contract).
5. No tokens or upstream bodies appear in error responses or server logs — visual on green-phase showboat.

## Implementer
hardener (per athena routing — same pane that landed fbb5896 / 370f9fa / 3345dbb / 4227474)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.16.6-7/transcript.md`
