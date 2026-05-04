# Writer — questions for direct code-read (oracle dead)

Five questions blocking final-pass prose. Each one I can write around in the
rough pass; each one needs a sourced answer before the full pass.

## 1. Implementation count — 7 or 8?

README.md (head of repo) lede says "Seven artifacts across three languages
and four mDNS libraries". The table directly under it lists 8 rows:

  saturn, ai-sdk-provider-saturn, vlc_extension, saturn-router,
  opencode-saturn (fork), owui_saturn.py, saturn-mcp, saturnd

Question: which is canonical per the thesis (Saturn.md)? Is `opencode-saturn`
counted (it's a fork, lives outside the monorepo) or excluded? Same question
for `saturnd` (Go) — was it part of the thesis-time count or a post-thesis
addition?

Where to look: Saturn.md around lines 939–965 (Table 4.1) and 1036–1041.

## 2. TXT field stability — MUST/SHOULD/MAY?

Current README/docs use "required / conditional / optional". DOCS_PATTERNS
wants RFC-style MUST/SHOULD/MAY for the spec/reference. I drafted
docs/reference/protocol/txt-keys.md with my best read:

  version, api_type, deployment, priority           → MUST
  api_base, ephemeral_key   (when deployment=cloud) → MUST
  rotation_interval         (when ephemeral_key set)→ SHOULD (default 300)
  features                                          → MAY

Question: does the thesis or v0.2 spec already declare these stability
levels? If not, are these the right defaults?

Where to look: docs/spec/v0.2/wire-format.md, Saturn.md around the TXT
schema discussion.

## 3. Health endpoint path — /v1/health or /health?

Inconsistency in the existing tree:

  README.md                            → GET /v1/health
  (deleted) developer-guide/protocol.md → GET /health
  saturn/web.py implementation         → ?

Question: which is the normative path? If /v1/health, is /health a
deprecated alias or an outright bug in the developer-guide page?

Where to look: saturn/web.py, saturnd/cmd/saturnd, ai-sdk-provider-saturn
sources.

## 4. Ephemeral key cadence — protocol invariant or impl detail?

Current README says "10-minute JWT rotated every 5 minutes" and cites
Saturn.md:609–625. txt-keys.md just merged calls `rotation_interval`
SHOULD-default-300.

Question: are the 600 s expiry and 300 s rotation cadence:
  (a) protocol invariants — every conformant beacon MUST use them,
  (b) reference-implementation defaults that browsers should NOT assume, or
  (c) suggested ranges with floor/ceiling MUSTs (e.g. expiry MUST be ≤ N)?

This shapes whether I write "Beacons MUST rotate every 5 minutes" or
"The reference Python beacon rotates every 5 minutes by default".

Where to look: Saturn.md:609–625 and Saturn.md:1334–1344, plus the Python
beacon source (saturn/beacon.py or similar).

## 5. Spec version naming — does v0.2 ≠ TXT version=1?

DOCS_PATTERNS wants spec/v0.1/, spec/v0.2/ subdirectories with stability
markers. The TXT carries `version=1`. I created docs/spec/v0.2/ around
the existing saturn-v2-* docs and asserted in spec/index.md that "v0.2
spec → TXT version=1".

Question: is that correct? Or does the thesis use a single version axis
(v1, v2 with no minor) and DOCS_PATTERNS' v0.x scheme is foreign?

Where to look: docs/spec/v0.2/proposal.md and wire-format.md headers,
Saturn.md.

---

## Plan if no answers come back before final pass

- Q1: drop the count from prose; let the table speak. ("The reference set
  spans five languages and four mDNS libraries.")
- Q2: keep MUST/SHOULD/MAY in txt-keys.md but mark the page "draft —
  pending spec sign-off".
- Q3: standardize on whatever `saturn/web.py` actually serves; add an alias
  note if the other path was historically used.
- Q4: write defensively ("the reference Python beacon ...") unless thesis
  says otherwise.
- Q5: rename docs/spec/v0.2/ → docs/spec/v1/ if direct read shows the
  thesis uses single-axis versioning.
