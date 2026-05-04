# Writer — May04 outline & catalogue

Working notes for Saturn-qj5.11 (README) and qj5.12 (docs/) while waiting on
gullivan's pattern files (qj5.10 README_PATTERNS.md, qj5.9 DOCS_PATTERNS.md).

## 1. Catalogue: current README — what to keep, cut, change

Current README.md is already researcher-grade (sourced to Saturn.md line refs,
no marketing fluff). Strengths to preserve:

- Opening graf already names the protocol identifier (`_saturn._tcp.local.`)
  and explicitly disclaims the Python package framing.
- "What the protocol asserts" / "What it does *not* claim" pair is good
  thesis-derived structure — keep.
- Reference-implementations table is the single best 5-second-decision
  artifact in the repo.
- Quickstart already orders shell → Go → Python (protocol-first).

Weaknesses to fix:

- Reference-implementations table lists 8 rows under a "Seven artifacts"
  sentence — count is wrong.
- Quickstart "From Python" still leads with `pip install -e .` against a
  cloned repo; should mirror docs which use `pip install saturn-ai`.
- Cloud-backends section mixes provider naming (`saturn openrouter` /
  `saturn deepinfra`) with a `.env.example` reference — Python-implementation
  detail leaking into the protocol README.
- Evaluation table footer ("at N=10, M=100 ...") repeats numbers that are
  already in claim 2 — collapse.
- Troubleshooting block duplicates the shell-quickstart commands.
- No code block showing a TXT record in raw `key=value` form (the wire
  artifact). Researchers want to see the bytes.
- No `curl` against `/v1/chat/completions` end-to-end (only `/v1/models`).
- AGENTS.md pointer is buried under the lede; a researcher landing on the
  page will not see a "what to read next" footer.

## 2. Catalogue: docs/ — repetition, structural debt

Hard duplicates (byte-identical or near-identical), to consolidate:

- `developer-guide/{protocol,python-package,router,mcp-tools,security,
  beacons,discovery,ai-sdk-provider}.md` ≡ `reference/<same>.md`.
  Pick one tree. Reference is the right home — it is what mkdocs.yml
  surfaces; developer-guide is the orphan.
- `user-guide/web-ui/*` ≡ `web-ui/*` (chat, models, mcp-tools, cost-tracking,
  remote, system, index/overview).
- `getting-started/quickstart.md` and `user-guide/quickstart.md` overlap
  ~70%; same for troubleshooting.md and faq.md.

Python-centric phrasings that violate "Saturn = protocol, not package":

- `docs/index.md` "Try the protocol → From Python — `pip install saturn-ai`"
  — ordering is fine, but the section frames Python as the default install
  rather than as one implementation. Move Python below Go.
- `docs/getting-started/quickstart.md` line 41: `pip install saturn-ai`
  presented as the canonical install. Should follow the README pattern
  (shell first, Go second, Python third).
- `docs/integrations/*` — most pages assume the Python `saturn` CLI is the
  service producer. Flag for gullivan: integration pages should describe
  what the integration consumes (`_saturn._tcp.local.` advertisements) and
  show *any* conformant implementation, not Python specifically.
- `docs/reference/api.md` (291 lines) likely the deepest debt — review
  after pattern files arrive.

Missing from docs/ that the README has:

- The five thesis claims with line-reference citations.
- The role-cost asymptotic form (`12 + 19N + 7M` vs `14 + 4N + 0M`).
- Threats-to-validity / what Saturn does *not* claim.

Missing from docs/ that neither has:

- A "Conformance" page: what does it mean to *be* a Saturn implementation?
  Required TXT fields, required endpoints, required streaming format.
  This is the document a researcher writing a fourth-language client wants.
- A `mdns-os-research.md` is present (1473 lines) but unindexed in
  mkdocs.yml — confirm with athena whether it should be linked.

## 3. README outline (5-second-decision bar)

Target: a researcher reads the first screenful, knows whether Saturn is
worth their afternoon.

```
# Saturn

[1-sentence what + 1-sentence why, both already in the existing lede]

> AI agents → AGENTS.md
> ML systems researchers → docs/SATURN_FOR_ML_SYSTEMS_RESEARCHERS.md

## In 60 seconds

  ```bash
  dns-sd -B _saturn._tcp local.            # macOS
  avahi-browse -rtp _saturn._tcp           # Linux
  curl http://<host>:<port>/v1/models      # any conformant instance
  ```

  ```text
  # one Saturn TXT record, on the wire:
  version=1 api_type=openai deployment=cloud priority=10
  api_base=https://openrouter.ai/api/v1
  ephemeral_key=eyJhbGc... (10-min JWT, rotated every 5)
  features=chat,tools,vision
  ```

## What the protocol asserts                 [5 claims, citations — keep]
## What it does not claim                    [3 disclaimers — keep]

## Reference implementations
  [table — fix row count, keep as-is otherwise]

## Quickstart
  ### Shell  — `dns-sd` / `avahi-browse` + `curl`
  ### Go     — `saturnd`
  ### Rust   — `saturn-router` (1-line cargo install or cross-compile pointer)
  ### TS     — `ai-sdk-provider-saturn` (one snippet)
  ### Python — `saturn-ai` (one snippet, no `pip install -e .`)

## Roles                                     [keep — concentrated complexity]
## Evaluation summary                        [keep table; drop redundant tail]
## Troubleshooting                           [drop duplicate commands; keep
                                              the AP-isolation/UDP-5353 note]
## Contributing                              [keep]
```

Codeblock budget: minimum 6 fenced blocks before the first H2 below
"Quickstart". Currently the README has 3 in that range.

Repetition to remove: the `dns-sd -B _saturn._tcp local.` command appears
3× in the current README. Goal: 1×, in In-60-seconds.

## 4. docs/ structure outline

Two top-level audiences. Mirror that in the IA.

```
docs/
  index.md                         landing — keep, light touch
  who-is-this-for.md               role cards → links into the right tree

  protocol/                        the spec (what *is* Saturn)
    overview.md                    1-page: records, endpoints, TXT schema
    txt-schema.md                  the wire format with byte counts
    endpoints.md                   /v1/health, /v1/models, /v1/chat/completions
    discovery-flow.md              browse → resolve → select → call
    beacons.md                     credential-dispensing, no proxying
    conformance.md                 NEW: how to write a 4th implementation
    security.md                    threat model, AP-isolation, secret rotation

  implementations/                 the seven artifacts (was reference/)
    python.md
    typescript-ai-sdk.md
    rust-router.md
    go-saturnd.md
    lua-vlc.md
    open-webui.md
    saturn-mcp.md

  guides/                          task-shaped, codeblock-heavy
    run-a-service.md               any backend, any language
    discover-from-shell.md
    discover-from-go.md
    discover-from-python.md
    deploy-on-openwrt.md
    using-ollama.md
    using-cloud-backends.md        OpenRouter, DeepInfra

  web-ui/                          one tree, not two
    overview.md, chat.md, models.md, mcp-tools.md, cost-tracking.md,
    remote.md, system.md

  research/
    SATURN_FOR_ML_SYSTEMS_RESEARCHERS.md   (existing)
    mdns-os-research.md                     (existing — index it)
    saturn-v2-proposal.md                   (existing)
    saturn-v2-technical-spec.md             (existing)

  reference/                       generated / mechanical
    api.md                         keep — full HTTP reference
    cli.md                         saturn(1)-style page
    config-toml.md, env-vars.md    moved from configuration/

  faq.md, troubleshooting.md       single copy each
```

What gets deleted:

- `developer-guide/` (duplicate of `reference/`).
- `user-guide/` (duplicate of top-level web-ui/ + getting-started/).
- `getting-started/` collapses into top-level `guides/` + `faq.md` +
  `troubleshooting.md`.
- One of the two `quickstart.md` files.

What stays Python-only (and is labelled as such):

- `implementations/python.md` — `pip install saturn-ai`, `saturn` CLI.
- `web-ui/*` — the Web-UI is part of the Python package; that's fine, it
  just needs to be named as a Python-package surface, not as "Saturn the
  protocol's UI".

## 5. Open questions for oracle (before drafting prose)

1. Row count: README says "Seven artifacts" but the table has 8. Thesis
   number?
2. Conformance: does the thesis specify which TXT fields are MUST vs SHOULD
   vs MAY? The README table uses required/conditional/optional —
   confirm those align with the spec.
3. `/v1/health` vs `/health`: README says `/v1/health`, developer-guide
   says `/health`. Which is normative?
4. The 10-min JWT / 5-min rotation cadence — is that the thesis-claimed
   cadence or an implementation choice? The README cites Saturn.md:609–625;
   want oracle to confirm before quoting it as a protocol invariant.

I will ping oracle on these once the pattern files are in and I'm drafting.

## 6. Status

- Saturn-qj5.11: in_progress, BLOCKED on qj5.10 (README_PATTERNS.md).
- Saturn-qj5.12: in_progress, BLOCKED on qj5.9 (DOCS_PATTERNS.md).
- This outline is the pre-draft scaffold. Two-pass plan: rough → full,
  README first, then docs/.
