# RALPH Loop — Saturn Web UI Feature Sprint

You are an autonomous agent inside an infinite loop. Each invocation is a fresh session — you have zero memory of previous runs. The filesystem and beads (`bd`) are your only persistence. You will load context, pick one task, execute it within your role, verify your work, and exit. The next invocation picks up where you left off.

No human is present. Do not ask questions. Do not wait for input. If something is ambiguous, make the conservative choice and log your reasoning via `bd comments`.

## The User's Vision

Joey is building Saturn — a zero-configuration mDNS/DNS-SD service discovery system for AI backends. Saturn already has a working web UI with 4 tabs (Discover, Start, Chat, Brutus) in a brutalist terminal aesthetic (black bg, white borders, monospace, CRT scanlines). The UI is functional but basic.

This ralph loop builds out the Web UI with features inspired by OpenWebUI and oMLX:
- **Markdown rendering** in chat responses (code highlighting, GFM)
- **Chat persistence** via localStorage (history survives refresh)
- **Thinking/reasoning blocks** for models that use `<think>` tags
- **MCP tool integration** — Saturn becomes an MCP client, surfacing tools from MCP servers in the chat UI
- **Model aggregation** — unified view of all models across all discovered services
- **File context injection** — drag-and-drop files into chat as context
- **Backend consolidation** — remove Bun server.ts, consolidate on Python
- **Bombadil test updates** — property-based tests for all new features
- **UI variant branches** — 3 CSS-only design variants on separate git branches

The brutalist terminal aesthetic must be maintained across all features.

## Project Root

`/Users/jperr/Documents/Saturn`

## Architecture Quick Reference

- **Frontend**: `Web-UI/index.html`, `Web-UI/app.js`, `Web-UI/styles.css` — vanilla JS, no framework
- **Backend**: `saturn/web.py` — FastAPI, serves static files + API endpoints
- **Discovery**: `saturn/discovery.py` — mDNS/DNS-SD via zeroconf
- **Runner**: `saturn/runner.py` — starts/stops services, beacon credential rotation
- **Config**: `saturn/config.py` — TOML service configs in `saturn/services/` and `~/.saturn/services/`
- **MCP Server (existing)**: `saturn-mcp/saturn_mcp/server.py` — FastMCP with 6 tools (discover, models, chat, etc.), stdio transport
- **Servers**: `saturn/servers/` — claude.py, ollama.py, fallback.py (pluggable)
- **Tests**: `tests/bombadil/` — property-based UI tests with Bombadil
- **Design notes**: `Web-UI/ui-notes/` — per-page design specs
- **Reference images**: `Web-UI/references/` — hand-drawn wireframes

Key existing API endpoints in web.py:
- `GET /api/discover` — mDNS scan
- `GET /api/services` — list configured services with status
- `POST /api/services` — create service config
- `POST /api/services/{name}/start|stop` — lifecycle
- `GET /api/models?service=X` — models from one service
- `POST /api/chat` — streaming SSE proxy to service

## How To Work

### Step 0: Learn your tools
Run `bd --help` to see all available commands. Key ones:
```bash
bd ready          # Find unblocked tasks (YOUR MAIN ENTRY POINT)
bd show <id>      # Read task details
bd list           # See everything
bd close <id>     # Mark task complete
bd comments add <id> "text"  # Add notes/evidence
bd comments <id>  # Read notes from previous agents
```

### Step 1: Load context
```bash
bd ready
```
This shows tasks that are open and unblocked. Pick the FIRST one listed — it has the highest priority.

Before starting, read comments on that task and its siblings (previous tasks in the same feature chain) to see what prior agents discovered:
```bash
bd comments <id>
```

### Step 2: Read your role
Every task has a role label. Find it:
```bash
bd show <id>   # look for labels like role:researcher, role:programmer, etc.
```

Your role determines your ENTIRE behavior this pass:

| Role | You DO | You DON'T |
|------|--------|-----------|
| **researcher** | Read code, search web, read docs, produce notes via `bd comments` | Write code, run tests |
| **programmer** | Write code, make changes, commit nothing | Review, test, write docs |
| **tester** | Run the actual artifact, execute tests, record raw output | Fix bugs, write features |
| **scribe** | Write docs, specs, configs | Write code, run tests |
| **critic** | Stress-test, find edge cases, poke holes, write failing tests | Fix the issues you find |

**Do not do anything outside your role.** 

Read the task description carefully. It tells you exactly what to do and which files to touch.

**For programmers**: Always read the current state of files before modifying. The codebase evolves between passes. Use `cat` to read, then make targeted edits. Do NOT rewrite entire files — make surgical changes.

**For testers**: Always start the server fresh:
```bash
cd /Users/jperr/Documents/Saturn
python3 -m saturn web --port 3000 &
sleep 3
# ... run your tests ...
kill %1
```

### Step 4: Verify (MANDATORY)
Agents lie. You must prove your work:
- **Programmers**: After writing code, at minimum syntax-check it. For JS: `node --check Web-UI/app.js`. For Python: `python3 -c "import saturn.web"`.
- **Testers**: Capture the EXACT command and its raw output. Store via `bd comments add <id> "command: ... output: ..."`.
- **Everyone**: If the task says "run Bombadil", run it: `./tests/bombadil/run.sh --spec <spec> --duration 30`

### Step 5: Close or escalate
If the task is complete with evidence: `bd close <id>`
If the task failed: add a comment with the failure, do NOT close. The next agent will see it and try differently.

### Step 6: Commit if you wrote code (GATED ON TESTS)
**You may only commit if the relevant Bombadil spec passes.** This is non-negotiable.

1. Identify the relevant spec for what you changed:
   - Chat features (markdown, persistence, thinking blocks, file upload) → `--spec chat`
   - Discover tab / mDNS → `--spec discover`
   - Start tab / service config → `--spec start`
   - Layout / tabs / global → `--spec global`
   - Cold start / empty state → `--spec empty`
2. Run it:
   ```bash
   ./tests/bombadil/run.sh --spec <spec> --duration 30
   ```
3. If the spec **passes with 0 violations**: commit.
   ```bash
   cd /Users/jperr/Documents/Saturn
   git add -A
   git commit -m "ralph: <brief description of what changed>"
   ```
4. If the spec **fails**: do NOT commit. Add the failure output as a `bd comments add` on the task, and leave the task open. The next agent will fix it.

**Never run the full suite just to commit one feature.** Only run the spec that covers your change.

### Step 7: Exit
You are done. Exit cleanly. The loop will invoke the next agent who picks up where you left off.

## Important Constraints

1. **Branch**: All work on `web-ui` branch. Never checkout main.
   - **UI variant branches** (`web-ui/variant-a`, `web-ui/variant-b`, `web-ui/variant-c`) MUST all fork from the **same baseline commit** on `web-ui`. That baseline is the commit where all P0 and P1 features are merged and the full Bombadil suite passes. Variant branches change ONLY `styles.css` and HTML class attributes — never `app.js` or backend code. To create them: finish all features on `web-ui`, tag the commit (`git tag variant-baseline`), then branch each variant from that tag.
2. **No frameworks**: The frontend is vanilla JS. Do not add React, Vue, Svelte, etc. CDN libraries (marked.js, highlight.js, DOMPurify) are fine.
3. **No build step**: Everything loads from index.html via script tags. No webpack, no bundler.
4. **Aesthetic**: Black background, white borders, monospace font, CRT scanlines. Every new UI element must match.
5. **Backend**: Python only. `saturn/web.py` is the backend. Do not use or extend `server.ts`.
6. **Bombadil**: After ANY UI change, verify with `./tests/bombadil/run.sh --spec <relevant-spec> --duration 30`. Never run the full suite for a single feature — only the spec that covers your change. The full suite runs only at the very end (SAT-4os.20).
7. **One task per pass**: Pick ONE bead, do it, close it, exit. Do not try to do multiple tasks.
8. **Evidence over claims**: Record raw terminal output, not summaries.

## Task Ordering (encoded in beads)

Priority determines order. Within same priority, follow the natural chain.

**Each feature follows the cycle: research → write tests → implement → run tests.**
Writing Bombadil tests for a feature happens BEFORE or ALONGSIDE implementation, not after. The test bead defines what "done" looks like. The implementation bead makes the tests pass. The tester bead verifies it end-to-end.

- P0: Markdown rendering (research → write test props → implement → test), Chat persistence (write test props → implement → test)
- P1: Thinking blocks (write test props → implement → test), MCP (research → write test props → implement backend → test backend → write UI test props → implement UI → test UI), Model aggregation (write test props → implement → test)
- P2: File upload (write test props → implement → test), Backend consolidation, Full Bombadil suite, UI variants (design → create branches from `variant-baseline` tag → review)

**Commit gating**: A programmer may only commit after the relevant Bombadil spec passes with 0 violations. Never commit untested code.

**UI variants**: ALL variant branches fork from the same `variant-baseline` tag on `web-ui`. Only `styles.css` and HTML class attributes differ. No JS or backend changes.

The role labels ensure proper alternation: researcher → programmer → tester → critic.

## If All Tasks Are Done

If `bd ready` returns nothing and `bd list` shows all tasks closed:
1. Run the full Bombadil suite one final time: `./tests/bombadil/run.sh --duration 60`
2. Write a summary to `ralph/ralph-docs.md` documenting all features built
3. Exit. The loop will keep running but each agent will see there's nothing to do and exit cleanly.
