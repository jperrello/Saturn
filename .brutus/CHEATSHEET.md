# Brutus contract patterns — cheatsheet

Captured during the MAY05 promo-push. Patterns that have shipped 30+ green
contracts. Reference for future brutus runs.

---

## 1. Contract shape

Each contract lives at `.brutus/Saturn-<id>/` with three files:

- `CONTRACT.md` — spec restatement, oracle, run command, captured red,
  fix sketch, out-of-scope, implementer.
- `transcript.md` — `showboat`-captured red phase + green phase.
- `VERDICT.md` — written ONLY after green is observed; cites the
  implementer's commit sha.

Test files live at `saturn/tests/test_<topic>_<bead>.py` with a one-test-per-
falsifiable-bullet shape.

## 2. The red-phase tax

A test that passes on first run "is decoration, not a contract" (CLAUDE.md
house rule). Three exits:

- **Real new behavior missing** → red, ship.
- **Test passes immediately** → either the behavior already works (write
  it as a *regression-guard* contract — explicitly note "no red phase,
  preserve-behavior") or the oracle is too loose (tighten).
- **Red for the wrong reason** (import error, typo, fixture flake) → fix
  the test until red shape is "behavior is missing."

Saturn-oqm, Saturn-b3o, Saturn-ggn are valid regression-guard contracts.
House rule: "If the change is meant to preserve behavior, the contract is
that the existing test suite still passes — verify it."

## 3. NO MOCKS — the hierarchy

RUN_BRIEF_MAY05 hard rule: "no mocks in tests. Real backends, real LLMs,
real Saturn services, real network."

Decoder ring:

| Pattern | Allowed? | Why |
|---|---|---|
| `mock.patch("requests.post", ...)` | ❌ | Mocking the upstream protocol |
| `monkeypatch.setattr(saturn.web, "_failover_state", FakeMap())` | ✅ | Test-boundary control of Saturn's own internal state |
| `monkeypatch.setenv("SATURN_PREFER_V6", "1")` | ✅ | Env var injection |
| `monkeypatch.setattr(psutil, "net_if_addrs", lambda: ...)` | ✅ (note in contract) | OS-API test-boundary control; not a service mock |
| Spawning a real `mcp.server.FastMCP` subprocess as a "fake peer" | ✅ | Real protocol, real bytes on the wire |
| Hardcoding `127.0.0.1:1` to simulate "unreachable" | ✅ | Real TCP attempt |

When in doubt, document the choice in the contract's "## Test rig (no mocks)"
section.

## 4. Subprocess peer pattern (the cbt.4 / fake-MCP shape)

For tests that need a real upstream (Saturn peer, MCP server), embed the
peer source in the test file as a `_SRC = textwrap.dedent('''...''')`
constant, write to `tmp_path`, spawn:

```python
@pytest.fixture
def peers(tmp_path):
    src = tmp_path / "peer.py"
    src.write_text(PEER_SRC)
    procs = []
    descriptors = []
    try:
        for name in ("peer-a", "peer-b"):
            port = _free()
            state_file = tmp_path / f"{name}.state.json"
            state_file.write_text(json.dumps({"health_ok": True}))
            env = {**os.environ, "PEER_NAME": name, "PEER_PORT": str(port),
                   "PEER_STATE_FILE": str(state_file)}
            log = open(tmp_path / f"{name}.log", "wb")
            proc = subprocess.Popen([sys.executable, str(src)], env=env,
                                    stdout=log, stderr=log)
            procs.append(proc)
            assert _wait_up(f"http://127.0.0.1:{port}/v1/health"), \
                f"{name} did not come up; see {tmp_path / f'{name}.log'}"
            descriptors.append({"name": name, "port": port, ...})
        yield descriptors
    finally:
        for p in procs:
            try: p.terminate()
            except Exception: pass
        for p in procs:
            try: p.wait(timeout=3)
            except Exception:
                try: p.kill()
                except Exception: pass
```

Per-test config goes via env vars (the peer reads them once at startup) or
via a JSON state file the peer re-reads on every request (lets tests flip
behavior mid-fixture: `_set_state(peer_a, chat_500=True)`).

Examples in tree: `saturn/tests/test_failover_cbt4.py`,
`saturn/tests/conftest_mcp.py` (FastMCP fake server).

## 5. In-process TestClient + injected `_discovered`

For testing saturn web logic without spinning the full process:

```python
@pytest.fixture
def app_client(peers, monkeypatch):
    from fastapi.testclient import TestClient
    import saturn.web as W
    admin_token = "test-" + secrets.token_urlsafe(16)
    monkeypatch.setenv("SATURN_ADMIN_TOKEN", admin_token)
    W._discovered.clear()
    W._breakers.clear()
    if hasattr(W, "_failover_state"):
        W._failover_state.clear()
    for d in peers:
        W._discovered[d["name"]] = {"name": d["name"], "host": "127.0.0.1",
                                    "port": d["port"], ...}
    client = TestClient(W.app)
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    yield client, peers
    W._discovered.clear()
```

Faster than the subprocess approach when you only need to exercise saturn
web's request handling. Pair with subprocess peers for upstream realism.

## 6. Showboat capture

Every contract MUST land a transcript:

```bash
mkdir -p .brutus/Saturn-<id>
uvx showboat --workdir <project-root> init <project-root>/.brutus/Saturn-<id>/transcript.md "<title>"
uvx showboat note <transcript> "<spec restatement; one paragraph>"
uvx showboat --workdir <project-root> exec <transcript> bash 'export PATH=".venv/bin:$PATH" && cd <project-root> && python -m pytest <test> --no-header -rN --tb=line 2>&1 | tail -8'
```

The `--workdir` + explicit `PATH` matter: showboat-via-uvx can otherwise
spawn `python3` from the system, missing the venv.

For green capture (after implementer ships): `uvx showboat note` describing
the green + another `exec` to capture the passing run.

## 7. Test-runner invocation

Always run via the venv-installed pytest, not `pytest` from PATH:

```bash
PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" python -m pytest <file> \
  --no-header -rN --tb=line
```

`--tb=line` for status batches; `--tb=short` when investigating; `--tb=long`
only when a single test is mysteriously failing.

## 8. Oracle-design heuristics

- **Single-bullet RED tests** are the strongest gate. Multi-bullet tests
  pass-or-fail as a unit, hiding which sub-assert is regressing.
- **OR-shape oracles** are appropriate when the implementer has policy
  freedom (Saturn-eic: hard-reject OR truncation flag OR silent cap).
  Spell out all three accepted shapes in the assertion message.
- **Bound thresholds with units in the message** ("must be <2s wall clock";
  "must be ≤ 16 chars; got len=…"). Helps the implementer parse what
  changed in seconds.
- **Always include the file:line in the assertion message**: `"saturn/web.py:1062"`.
  Saves the implementer one grep.

## 9. Decomposition rule

A bead with 2+ orthogonal sub-features is a laundry list. Refuse.
Decompose to `.{a,b,c,d}` sub-beads (cbt.2 → cbt.2.{a,b,c,d}; cbt.3 →
cbt.3.{a,b,c,d}). Each sub-bead gets its own contract.

If the user pushes back: "give me one at a time."

## 10. Fold-into-existing pattern (audit findings)

When a security audit (or similar) lands new findings that overlap an
existing contract:

- **Amend** the contract; bump status to "AMENDED".
- **Add** a new RED test to the existing test file (or a new sibling file).
- **Reopen** the bd if it was closed.
- **Cite** the audit (geoff's `PARITY_REVIEW_MAY05.md`, `SECURITY_AUDIT.md`).

Don't file new beads for findings that decompose into the original surface.
DO file new beads for findings on a surface the original contract didn't
touch (Saturn-x9c, Saturn-zt2 are correct as new beads — they touch
modules cbt.7.advertise / cbt.5.1 didn't probe).

## 11. Hand-off message shape

```
Saturn-<id> CONTRACT READY: .brutus/Saturn-<id>/CONTRACT.md.
N failing test(s) at saturn/tests/<file>.py.
Run: cd <project> && PATH=<venv> python -m pytest <file>.
[1-line cite of geoff/joey/spec source]
Suggested implementer: <name>. ETA: ~Xmin.
```

Concise. Athena routes; hardener picks up; brutus VERDICTs on green callback.

## 12. VERDICT shape

```markdown
# VERDICT — Saturn-<id>

**Status:** GREEN.
**Implementer:** <name>.
**Implementation commit:** `<sha>`.

```
<rerun command>
N passed, 1 warning in Xs
```

<one-paragraph attestation>

[follow-up sub-beads, if any, named explicitly]

Transcript: `.brutus/Saturn-<id>/transcript.md`.
```

## 13. Red-but-no-greens guard

Before writing a VERDICT: re-run the test. If RED, do NOT write the
verdict. Report the discrepancy to the router with raw failure shapes.
Brutus does not fabricate attestations. (See the wave-2 "queue cleared
but git shows no commits" episode for the precedent.)

## 14. When NOT to author

- **UI-only beads** (Bombadil/Playwright .ts surfaces) → route to forge/UI lane.
- **Cross-language harnesses brutus can't drive** → route to the language owner.
- **Open-ended "make it faster" / "fix the bug" intents** → push back. Demand
  a measurable threshold or a regression case before opening the editor.

## 15. Idle burn options

When hardener queue is full and nothing's blocked on you:

- Pre-author follow-up sub-beads called out in existing contracts'
  out-of-scope sections.
- Fold any newly-landed audit findings into existing contracts.
- Update this CHEATSHEET when patterns emerge.
- Verify long-tail green tests still pass (catch silent regressions).
