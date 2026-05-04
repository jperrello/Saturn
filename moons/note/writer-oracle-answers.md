# Writer — sourced answers (oracle read)

## 1. Implementation count — 7 or 8?

**CANONICAL: 7 (thesis-time count)**

Saturn.md:976 explicitly: "these seven artifacts span three languages and four mDNS libraries." The thesis canon is saturn, saturn-router, vlc_extension, owui_saturn.py, saturn-mcp, ai-sdk-provider-saturn, saturnd.

**Excluded:** opencode-saturn (external fork, not monorepo, post-thesis addition). README's 8-row table reflects post-thesis work; Saturn.md Table 4.1 (lines 939–965) + Result 3 (lines 1036–1041) confirm seven.

---

## 2. TXT field stability — MUST/SHOULD/MAY?

**NOT DECLARED in existing specs.**

Saturn.md:568–603 (Table 3.1) and docs/spec/v0.2/wire-format.md:504–526 both use informal "Required / Conditional / No" — no RFC 3119 MUST/SHOULD/MAY. Your draft txt-keys.md is the first RFC-style formalization. Mark as "draft — pending spec sign-off" per Q2 fallback plan.

---

## 3. Health endpoint path — /v1/health or /health?

**NORMATIVE: `/v1/health`**

saturn/web.py:705–707 serves `@app.get("/v1/health")` — this is the actual implementation. README.md line 31 documents `/v1/health`. Aligns with `/v1/models` and `/v1/chat/completions`. Saturn.md:531–532 cites GET /health in spec text but deployed code (web.py) normalizes to `/v1/health`. The older developer-guide reference to `/health` is outdated.

---

## 4. Ephemeral key cadence — protocol invariant or impl detail?

**REFERENCE-IMPLEMENTATION DEFAULTS (not protocol invariants).**

Saturn.md:614–615 says "The default lifecycle uses a ten-minute key lifetime and a five-minute rotation interval" — describes defaults, not MUSTs. saturn/runner.py:80–86 sets `rotation_interval=300` and `expiration_interval=600` as configurable defaults. Saturn.md:609–625 is explanatory context, not prescriptive. Write defensively: "The reference Python beacon rotates every 5 minutes by default" — do NOT claim every conformant beacon MUST.

---

## 5. Spec version naming — does v0.2 ≠ TXT version=1?

**DUAL NAMING SCHEME: TXT carries single-axis `version=1`, docs proposed multi-axis `v0.2`.**

Saturn.md:573–575 defines TXT `version` field as "Protocol version (currently 1)" — single integer. docs/spec/v0.2/wire-format.md:1 headers as "Saturn v2 mDNS Technical Specification." The wire-format.md proposes `v=2` as a redesigned schema (lines 510–526), not yet canonical. Mapping: TXT `version=1` is the thesis-time schema; proposed `v=2` in wire-format.md is draft future redesign. DOCS_PATTERNS' `v0.1/v0.2` subdirectory scheme is orthogonal to the single-axis TXT versioning; clarify in spec/index.md that v0.2/ is the *proposed* v2 redesign, not canonical.

