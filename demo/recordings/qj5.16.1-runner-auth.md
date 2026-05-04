# qj5.16.1 — Runner /v1/* bearer auth

*2026-05-04T19:43:44Z by Showboat 0.6.1*
<!-- showboat-id: 91699d47-f3b7-45d8-9c5d-3b65682368d5 -->

Defensive capture of the auth gate added in commit fbb5896. The Saturn runner refuses every /v1/* request unless the caller presents a bearer token matching `SATURN_RUNNER_TOKEN` (HMAC-compared in saturn/runner.py:auth). 401 responses include `WWW-Authenticate: Bearer` per RFC 6750.

## Reproducer

The script below writes a default-runner config (no `server.module`, so the auth dependency is reachable), spawns the runner with a fresh token, and probes `/v1/health` three ways: no bearer, wrong bearer, correct bearer.

```bash
bash demo/recordings/runner_auth_probe.sh
```

```output
── (a) no bearer ──
HTTP/1.1 401 Unauthorized
date: Mon, 04 May 2026 19:43:48 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 25
content-type: application/json

HTTP 401

── (b) wrong bearer ──
HTTP/1.1 401 Unauthorized
date: Mon, 04 May 2026 19:43:48 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 25
content-type: application/json

HTTP 401

── (c) correct bearer ──
HTTP/1.1 200 OK
date: Mon, 04 May 2026 19:43:48 GMT
server: uvicorn
content-length: 118
content-type: application/json

HTTP 200

```

## Notes

- Implementation: `saturn/runner.py:351-365` (token loaded from env, `hmac.compare_digest` for the comparison).

- Routes covered: `/v1/health`, `/v1/models`, `/v1/chat/completions`.

- Caveat (Saturn-8v5, P1): configs that pin `server.module` (built-in ollama / claude / fallback) import `mod.app` directly, bypassing this dependency. Default-runner configs — like the harness fixtures and this reproducer — exercise the gate as intended.
