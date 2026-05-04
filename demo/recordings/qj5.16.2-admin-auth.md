# qj5.16.2 — Web admin /api/* bearer auth

*2026-05-04T19:46:12Z by Showboat 0.6.1*
<!-- showboat-id: 2079d928-2635-4f47-bf4f-8d106293b8bb -->

Defensive capture of the admin gate added in commit 370f9fa. The Saturn web UI refuses every /api/{services,admin,system,mcp}/* request unless the caller presents a bearer token matching `SATURN_ADMIN_TOKEN` (HMAC-compared in saturn/web.py:require_admin). 401 responses include `WWW-Authenticate: Bearer` per RFC 6750.

## Reproducer

The script below picks a free port, spawns `saturn web` with a fresh `SATURN_ADMIN_TOKEN`, and probes `/api/services` three ways: no bearer, wrong bearer, correct bearer.

```bash
bash demo/recordings/admin_auth_probe.sh
```

```output
── (a) no bearer ──
HTTP/1.1 401 Unauthorized
date: Mon, 04 May 2026 19:46:14 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 25
content-type: application/json

HTTP 401

── (b) wrong bearer ──
HTTP/1.1 401 Unauthorized
date: Mon, 04 May 2026 19:46:14 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 25
content-type: application/json

HTTP 401

── (c) correct bearer ──
HTTP/1.1 200 OK
date: Mon, 04 May 2026 19:46:14 GMT
server: uvicorn
content-length: 2061
content-type: application/json

HTTP 200

```

## Notes

- Implementation: `saturn/web.py:require_admin` (Depends() on every /api/{services,admin,system,mcp}/* route).

- The static UI assets at `/` and `/index.html` remain unauthenticated; only the admin JSON API requires the bearer.

- The HTML chat page calls these endpoints from the browser; the page must inject the admin token before they succeed (see `Web-UI/app.js`).
