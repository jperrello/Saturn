# Saturn DOCS_PATTERNS — Writer Brief

Pattern library distilled from FastAPI, NATS, libp2p, Prometheus, python-zeroconf. Pass 1 (rough). Read this before touching `docs/`.

Saturn is a **protocol** (mDNS/DNS-SD-based). Docs must lead with curl + Go. Python is one implementation among many.

---

## 1. Information Architecture (Diátaxis-shaped)

Top-level nav, in this order:

1. **Quickstart** — 60-second "see it work" (one curl, one screenshot, one TXT record).
2. **Tutorial** — narrative, ~30 min, end with a working discovery exchange.
3. **How-To** — task-oriented recipes ("Advertise a service", "Filter by capability", "Run behind a firewall").
4. **Concepts** — what mDNS is, why DNS-SD, Saturn's TXT-record schema, threat model.
5. **Protocol Reference** — wire format, record types, TXT keys, error codes. THE source of truth.
6. **Implementations** — Go, Python, CLI. Each implementation gets its own subtree.
7. **Spec** — formal grammar, RFC-style, versioned.

Sidebar collapses by section. Search bar top-right (mandatory; copy what NATS/Prometheus do).

## 2. Landing Page — 30-Second Value Prop

Above the fold MUST have:

- One-line tagline: what Saturn is + who it's for. ("Local-network discovery for AI endpoints — zero config, zero registry.")
- 3–5 bullet feature list (FastAPI pattern: `Fast | Standards-based | Zero-dep`).
- A copy-pasteable curl that returns a real Saturn TXT record. No prose between tagline and curl.
- Two buttons: **Quickstart** and **Protocol Spec**.
- Implementation badges: Go / Python / CLI logos linking to subtrees (libp2p pattern).
- Optional: logos of who uses it / a one-line quote.

Do NOT put architecture diagrams above the fold. They go in Concepts.

## 3. Code Block Density & Style

- **Tabs** for `curl | Go | Python | CLI`. curl FIRST in every tab group. (Saturn-specific deviation from FastAPI's Python-only.)
- Every code block must be **runnable as-is**. No `...` placeholders unless explicitly marked `# elided`.
- Show output beneath input, in a separate fenced block prefixed `# →` or in a styled output box (FastAPI pattern).
- Inline comments preferred over prose-then-block.
- Multi-line shell: one `$` per command, no backslash-continuation unless necessary.
- Every page that introduces a new concept needs ≥1 code block in the first screen.

## 4. Reference Style

- **Grouped, not alphabetical.** Group by: TXT keys, record types, error codes, client API.
- Each entry: `signature` → 1-line description → "When to use" → minimal example → links to related entries.
- Stable anchor IDs (`#txt-cap`, `#error-conflict`) — these get linked from elsewhere.
- Version each reference page. Show "since v0.3" badges on new fields.

## 5. Anti-Patterns Observed (do not do)

- **python-zeroconf**: README-as-docs, no quickstart, no curl, no acknowledgment that other implementations exist. Saturn must NOT do this — it's the single biggest trap.
- **libp2p landing**: zero code on homepage. Forces you to pick a language before you see anything work. Saturn shows curl on homepage.
- Wall-of-text concept pages with no code (Prometheus overview leans this way — break up with diagrams + examples).
- Python-first framing when the thing isn't Python (this is Saturn's biggest risk given the existing `docs/` likely came from a Python POV).
- Missing search, no version selector, dead "Edit on GitHub" links, no last-updated timestamp.
- Reference docs that are auto-generated dumps with no examples.
- "Coming soon" pages in nav.

## 6. Saturn-Specific Implications

Given Saturn IS a protocol with multiple implementations:

- **Landing copy must say "protocol" in the first sentence.** Not "library", not "package".
- **curl example on homepage** must hit a Saturn responder via `dns-sd` or `avahi-browse` equivalent piped to a parser, OR show `saturn discover` CLI output. Pick one and make it work in 5 seconds.
- **Three top-level entry points**: `Use Saturn` (CLI / curl), `Build a client` (Go / Python), `Implement Saturn` (spec).
- **Move `SATURN_FOR_ML_SYSTEMS_RESEARCHERS.md` content** into a `for/researchers.md` how-to page; don't leave it loose at root.
- **`saturn-v2-proposal.md` and `saturn-v2-technical-spec.md`** belong under `spec/` with version prefixes.
- **`mdns-os-research.md`** belongs under `concepts/mdns-background.md`.
- **`getting-started/`** must contain a single `quickstart.md` that works end-to-end in <2 min, plus `tutorial.md` (longer).
- **`reference/`** must split into `protocol/` (wire format, TXT keys) and `clients/{go,python,cli}/`.
- **`integrations/`** stays but each page gets a curl + Go example before the Python one.

## 7. Five-Page Minimum Spec

Writer must produce at least these pages, each conforming to the structure shown:

1. **`index.md`** — landing. Tagline + 5 bullets + curl block + 2 CTAs + impl badges. <80 lines.
2. **`getting-started/quickstart.md`** — 5 steps, each with one code block, ends with "what just happened" + next-step links. Curl-first; Go and Python as tabs.
3. **`concepts/protocol.md`** — what Saturn is on the wire. ASCII diagram of an mDNS exchange + annotated TXT record + glossary. ≥3 code blocks.
4. **`reference/txt-keys.md`** — grouped reference. Every TXT key: name / type / required / since / example / notes. Table at top, anchored sections below.
5. **`implementations/index.md`** — matrix table (feature × Go/Python/CLI), then one subsection per impl with install + minimal example + link to deep docs.

Each page: H1, 1-paragraph summary under H1, TOC if >3 H2s, "Edit this page" link, "Last updated" stamp.

---

Pass 1. TODO pass 2: Bonjour/Avahi conventions, Pydantic + Poetry + Requests reference patterns, Gin/Echo Go-doc style, Consul/Cockroach operator-doc structure, OAuth/OPA spec-doc patterns, concrete Saturn page tree diff.
