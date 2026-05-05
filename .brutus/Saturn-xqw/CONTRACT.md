# CONTRACT — Saturn-xqw: api_base TXT trust → SSRF / route hijack (P1)

**Status:** RED. 14 hostile vectors fail; 1 safe-control passes.
**Implementer:** athena → hardener (P1, front-of-queue).
**Geoff cite:** `FAILOVER_SECURITY.md` §(B).

## Spec restatement (falsifiable)

`saturn/discovery.py:175` reads `api_base` straight from peer-asserted
TXT, and `saturn/discovery.py:115-119`'s `effective_endpoint` returns it
verbatim when `deployment="cloud"`. Both fields are peer-asserted. Any
host on the LAN can advertise `api_base=http://<attacker>` and Saturn
routes user chat content + bearer headers there.

The fix MUST neutralize hostile values via at least one of:

  (a) **Resolve-side:** `_to_service` rejects (sets `api_base=""`).
  (b) **Consume-side:** `effective_endpoint` returns the
      `http://{host}:{port}/v1` fallback or raises.

Geoff's recommendation: do both (defense in depth). Brutus pins the
oracle, not the implementation site.

Hostile classes the validator MUST reject:

| Class | Examples |
|---|---|
| Cloud-metadata link-local | `http://169.254.169.254/...` |
| Loopback | `http://127.0.0.1:9200/`, `http://localhost:9200/` |
| RFC-1918 | `10.x`, `172.16-31.x`, `192.168.x` |
| CGNAT | `100.64.0.0/10` |
| IPv6 loopback / link-local / ULA | `[::1]`, `[fe80::*]`, `[fc..]`, `[fd..]` |
| Non-`https://` cloud schemes | `ftp://`, `javascript:`, etc. |

Positive control: `https://api.openai.com/v1` MUST flow through unchanged.

## Test files

- `saturn/tests/test_api_base_ssrf_xqw.py` (added; 15 tests — 14
  hostile-class parametrized + 1 safe-control).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_api_base_ssrf_xqw.py --no-header -rN --tb=short
```

## Captured red

```
14 failed, 1 passed, 1 warning in 0.05s
hostile api_base 'javascript:alert(1)' flowed through unguarded.
effective_endpoint returned 'javascript:alert(1)'; api_base on SaturnService
is 'javascript:alert(1)'.
```

(Same shape across all 14 hostile vectors — every one passes through.)
Transcript: `.brutus/Saturn-xqw/transcript.md`.

## Oracle

Per hostile vector, **at least one** of:
- `s.api_base == ""` (resolve-side sanitization), OR
- `s.effective_endpoint` does NOT contain the hostile string and is NOT
  equal to it (consume-side fallback to `http://{host}:{port}/v1`), OR
- `s.effective_endpoint` raises.

For the safe vector, `s.effective_endpoint == "https://api.openai.com/v1"`.

## Fix sketch (non-binding)

```python
# saturn/discovery.py — new module-level helper
import ipaddress
import urllib.parse

def _safe_api_base(url: str) -> str:
    if not url:
        return ""
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return ""
    if u.scheme not in ("https",):
        return ""
    host = u.hostname or ""
    if not host:
        return ""
    if host in ("localhost",):
        return ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # public hostname — accept (DNS resolution at connect time)
        return url
    if (ip.is_loopback or ip.is_link_local or ip.is_private
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
        return ""
    # CGNAT 100.64.0.0/10 — `is_private` covers it on Python 3.4+ via the
    # _PRIVATE_NETWORKS list, but verify for the runtime version.
    return url
```

Apply at:
- `_to_service` (resolve-side) — `api_base=_safe_api_base(props.get('api_base', ''))`.
- `effective_endpoint` (consume-side) — `if not _safe_api_base(self.api_base): return f"http://{self.host}:{self.port}/v1"`.

Implementer free to deviate.

## Out of scope

- Operator-asserted allowlist for `api_base` per peer name. File as
  **Saturn-xqw.allowlist** if desired (Saturn-93w's allowlist machinery
  may share a code path).
- DNS-resolution-time re-validation (host could be a public DNS name
  that resolves into RFC-1918). Out of scope; would require connect-time
  hook. File as **Saturn-xqw.dns** if needed.
- Runner-side enforcement (`saturn/runner.py:116-122` consumes
  `effective_endpoint`). Once the resolve-side sanitizer is in place,
  the runner inherits the guarantee.
- Signed TXT (cryptographic peer-assertion). Future epic; out of P1
  scope.

## Implementer

athena → hardener. P1, front-of-queue. ETA ~15 min.

## Transcript

`.brutus/Saturn-xqw/transcript.md`
