# CONTRACT — Saturn-zor / cbt.4.sec.token: `/api/system/chat` admin-token gate

**Status:** AMENDED. Original 3 tests GREEN (auth gate landed `b6ab724`).
**+1 RED test** added folding geoff's audit P3 (BrutusChat.messages cap).
**Implementer:** athena → hardener (one-line Pydantic Field constraint).

## Spec restatement (falsifiable)

`saturn/web.py:1062-1063`'s `brutus_chat` handler has no auth dependency.
Other admin-scope endpoints in the same file uniformly use
`Depends(require_admin)` (e.g., `/api/system/status` line 1274,
`/api/services` line 470, all of `/api/system/tunnel/*`). The cbt.4
failover surface MUST match.

Oracle:

  - `POST /api/system/chat` with NO `Authorization` → **401**.
  - `POST /api/system/chat` with WRONG bearer token → **401**.
  - `POST /api/system/chat` with CORRECT admin token → **!= 401** (auth
    passes through to business logic; 502 is the expected outcome here
    because no backends are discovered in the test fixture).

## Test files

- `saturn/tests/test_system_chat_auth_zor.py` (added; 3 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_system_chat_auth_zor.py --no-header -rN --tb=short
```

## Captured red

```
test_no_auth_returns_401:    AssertionError: 502 != 401  (no auth gate)
test_wrong_token_returns_401: AssertionError: 502 != 401
test_correct_token_passes_auth: PASSED  (paired regression guard — auth
                                          must not reject legitimate tokens)
==================== 2 failed, 1 passed, 1 warning in 8.05s ====================
```

Transcript: `.brutus/Saturn-zor/transcript.md`.

## Oracle definition

| Test | Oracle |
|---|---|
| `no_auth_returns_401` | status == 401 |
| `wrong_token_returns_401` | status == 401 |
| `correct_token_passes_auth` | status != 401 (any other code) |

## Fix sketch

```python
# saturn/web.py:1062
@app.post("/api/system/chat")
async def brutus_chat(body: BrutusChat, request: Request, _=Depends(require_admin)):
    ...
```

One-line diff. The 401 envelope from `require_admin` already includes the
`WWW-Authenticate: Bearer` header per existing convention.

## Folded — geoff audit P3: BrutusChat.messages cap

`BrutusChat` (saturn/web.py:1035-1060) declares `messages: List[dict]`
with no Pydantic length cap. A 10001-element list is accepted today
(returns 502 only because no backends are available, not because of body
validation).

Add a Field constraint:

```python
from pydantic import Field
class BrutusChat(BaseModel):
    messages: List[dict] = Field(..., max_length=200)
    ...
```

The exact cap is the implementer's choice (200-500 is reasonable per
geoff's note; a real conversation rarely exceeds 100 turns).

New test: `test_oversized_messages_list_returns_422` (RED). Sends 10001
messages with valid auth; expects 422 from Pydantic. Currently 502.

## Out of scope

- Per-user / per-token authorization beyond the binary admin gate. File
  as **Saturn-zor.scopes** if RBAC lands.
- Token rotation, mTLS, signed-cookie variants — Joey listed these in the
  bead description as alternatives. The plain admin-token model is the
  cheapest fix that matches the rest of `/api/system/*`.
- Rate limiting — that is **Saturn-b3o** (cbt.4.sec.ratelimit), parallel
  contract.

## Implementer

athena → hardener. ETA ~5 min.
