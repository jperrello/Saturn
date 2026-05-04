# Saturn DOCS_PATTERNS — Writer Brief

Pattern library for the `docs/` rewrite. Distilled from FastAPI, NATS, libp2p, Prometheus, python-zeroconf, Pydantic, Requests, Echo (Go), Consul, OAuth 2.0, OPA, grandcat/zeroconf. Pass 2 (full).

**Saturn is a protocol** (mDNS/DNS-SD-based, for AI endpoint discovery). Docs MUST lead with curl + Go. Python is one implementation among many.

---

## 1. Information Architecture (Diátaxis-shaped)

Top-level nav, in this order:

1. **Quickstart** — 60-second "see it work". One curl, one screenshot, one TXT record.
2. **Tutorial** — narrative, ~30 min, ends with a working discovery exchange you built.
3. **How-To** — task-oriented recipes ("Advertise a service", "Filter by capability TXT key", "Run across subnets via unicast", "Debug with `dns-sd -B`").
4. **Concepts** — what mDNS is, why DNS-SD, Saturn's TXT-record schema, conflict resolution, threat model.
5. **Protocol Reference** — wire format, record types, TXT keys, error codes. THE source of truth, RFC-style.
6. **Implementations** — Go, Python, CLI; each gets its own subtree with its own quickstart + API reference.
7. **Spec** — formal grammar, versioned (`v0.1`, `v0.2`...), with stability markers (Draft / Stable / Deprecated — OAuth pattern).

Sidebar collapses by section. Search bar top-right (mandatory; copy NATS/Prometheus). Version selector top-left (Pydantic pattern). "Edit on GitHub" + "Last updated" stamp on every page (Consul pattern).

**Why this order:** Quickstart-first proves it works; Tutorial teaches; How-To answers "I have a job"; Concepts answers "why"; Reference answers "what exactly"; Implementations answers "in my language"; Spec answers "I'm building one".

## 2. Landing Page — 30-Second Value Prop

Above the fold MUST have:

- One-line tagline naming the protocol + audience: *"Saturn — local-network discovery for AI endpoints. Zero config, zero registry, RFC-grade."*
- 3–5 bullet feature list (FastAPI pattern: `Zero-config | RFC-based | Multi-language | Encrypted-aware | Sub-second discovery`).
- A copy-pasteable curl-or-CLI block that returns a real Saturn record. Single command. (Requests does this with a `>>>` REPL block; Saturn does it with `$ saturn discover` or `$ dns-sd -B _saturn._tcp`.)
- Two CTAs: **Quickstart →** and **Protocol Spec →**.
- Implementation badges row: Go / Python / CLI / (future) Rust — clicking goes to that impl's subtree (libp2p pattern).
- Optional below-fold: who uses it, one-line quote, architecture diagram.

Do NOT put architecture diagrams above the fold. Do NOT show Python `import` first. Do NOT bury the working command behind paragraphs.

## 3. Code-Block Density & Style

- **Tabbed code blocks for every cross-cutting example: `curl | Go | Python | CLI`.** curl/CLI FIRST in tab order (Saturn's deviation from FastAPI's Python-only).
- Every block must be **runnable as-is**. No `...` placeholders unless explicitly marked `# elided`.
- Show output beneath input as a separate block (FastAPI pattern), prefixed `# →` or in a styled "Response" box.
- Inline comments preferred over prose-then-block (grandcat/zeroconf pattern: comment shows the *why* on the line itself).
- Multi-line shell: one `$` per command, no backslash-continuation unless necessary.
- Every page that introduces a new concept needs ≥1 code block in the first screen-height.
- Streaming/async patterns: show channel/iterator usage explicitly (Go channels, Python `async for`, curl `--no-buffer`). Don't hand-wave.
- Use Echo/Gin pattern for Go: full `func main()` examples, not snippets that need imagined imports.

## 4. Reference Style

- **Grouped, not alphabetical.** Group by domain: TXT keys, record types, error codes, Resolver methods, Server methods.
- Each entry follows the OPA/grandcat pattern:
  ```
  signature              ← code-formatted
  one-line description   ← what it does
  When to use            ← 1–2 sentences
  Example                ← minimal working snippet
  See also               ← cross-links
  ```
- Stable anchor IDs (`#txt-cap`, `#error-conflict`) — these are linked from elsewhere.
- Version each reference page. Show `Since v0.3` badges on new fields, `Deprecated in v0.5` badges on old ones (OAuth pattern: visible maturity markers).
- Reference pages get a table-of-contents at the top (Requests pattern: long anchor list before content).
- For protocol reference: hex/wire dumps with annotated callouts, not just prose.

## 5. Anti-Patterns Observed

- **python-zeroconf**: README-as-docs. No quickstart, no curl, no acknowledgment that other implementations exist. Saturn must NOT do this — biggest trap given Saturn's history.
- **libp2p landing**: zero working code on homepage. Forces language choice before proof-of-life. Saturn shows curl on homepage.
- **Prometheus overview**: wall-of-text concept page with no code. Break up Concepts pages with diagrams + runnable snippets.
- **Echo landing (the page we got)**: vague marketing copy, no code. Don't.
- **Python-first framing** when the thing isn't Python — Saturn's #1 risk. Audit every page: if Python appears before curl/Go in a tab group, fix it.
- **Coming soon / TODO pages in nav.** Hide until written.
- **Auto-generated reference dumps with no examples.** Every reference entry needs a hand-written example.
- **Missing search**, no version selector, dead "Edit on GitHub", no last-updated stamp.
- **Multiple competing entry-points** ("Get Started" vs "Quickstart" vs "Tutorial" vs "Installation" — pick one Quickstart, link the rest from it).
- **Mixing protocol and library concerns on the same page.** Protocol pages describe wire bytes; library pages describe API calls. Cross-link, don't merge.
- **OAuth's mistake**: too many specs surfaced at once on the index. Mark "core" vs "extension" prominently.

## 6. Saturn-Specific Implications

Given Saturn IS a protocol with multiple implementations, the existing `docs/` (which currently mixes legacy index, ML-researchers prose, v2 spec drafts, mDNS-OS research) needs this surgery:

- **Landing copy says "protocol" in sentence one.** Not "library", not "package", not "framework".
- **Homepage curl/CLI** must hit a Saturn responder via `saturn discover` (or `dns-sd -B _saturn._tcp` piped to a tiny parser) and show real output. Build it before writing docs if it doesn't exist.
- **Three top-level routes** from the homepage: `Use Saturn` (CLI / curl) → `Build a client` (Go / Python) → `Implement Saturn` (spec). Pattern stolen from Consul's three-way Operations / API / CLI split.
- **File moves** (relative to `docs/`):
  - `SATURN_FOR_ML_SYSTEMS_RESEARCHERS.md` → `how-to/for-researchers.md`
  - `saturn-v2-proposal.md` + `saturn-v2-technical-spec.md` → `spec/v0.2/{proposal,wire-format}.md`
  - `mdns-os-research.md` → `concepts/mdns-background.md`
  - `LANDING.md` → merge into `index.md` (no two landings)
  - `index-legacy.html` → archive out of nav
  - `developer-guide/`, `user-guide/`, `getting-started/` — collapse: `getting-started/quickstart.md`, `tutorial/`, `how-to/`, `developer-guide/` becomes `implementations/`
  - `reference/` → split into `reference/protocol/` (TXT keys, wire format, errors) and `reference/clients/{go,python,cli}/`
  - `integrations/` stays; each page rewritten so curl + Go come before Python.
- **`llms.txt`** should be regenerated after the rewrite from the new IA, not edited in place.
- **`web-ui/` and `moons/`** are separate products — link out, don't intermix with protocol docs.
- **Every concept page** ends with "How this looks on the wire" — a hex/text dump of the relevant mDNS/DNS-SD record (Bonjour-style annotated diagram).
- **Every implementation page** opens with the same 5-line example doing the same thing (discover one service) — so readers can compare languages side-by-side.

## 7. Five-Page Minimum Spec

Writer must produce at least these pages, each conforming to the structure shown:

1. **`index.md`** — landing. Tagline + 5 bullets + tabbed curl/Go/Python/CLI block + 2 CTAs + impl badges + (below fold) one-paragraph "what is mDNS" + diagram. <120 lines.
2. **`getting-started/quickstart.md`** — 5 numbered steps, each with one tabbed code block (curl/Go/Python/CLI), each ending in shown output. Closes with "What just happened" recap + 3 next-step links (Tutorial / How-To / Reference). Total <300 lines.
3. **`concepts/protocol.md`** — what Saturn is on the wire. ASCII diagram of a query/response exchange + annotated TXT record + glossary table. ≥3 code blocks, ≥1 hex/text dump.
4. **`reference/protocol/txt-keys.md`** — grouped reference. Lead with a summary table (key / type / required / since). Below: anchored sections per key with `signature → 1-line → when to use → example → see also`.
5. **`implementations/index.md`** — feature matrix table (rows = features, columns = Go/Python/CLI, cells = ✓ / ✗ / partial). Below: one subsection per impl with install + the same 5-line "discover one service" example + link to that impl's deep docs.

Each page header convention: `H1 title` → 1-paragraph summary → TOC if >3 H2s → body → "Edit this page" link → "Last updated <date>" stamp.

---

**Source coverage (pass 2):** FastAPI, NATS, libp2p, Prometheus, python-zeroconf, Pydantic, Requests, Echo, Consul, OAuth 2.0, OPA, grandcat/zeroconf. Poetry doc fetch failed (ECONNREFUSED) — pattern inferred from peer projects. Bonjour/Avahi sites not crawled directly; assumptions drawn from grandcat README references to RFCs 6762/6763 and standard mDNS conventions.
