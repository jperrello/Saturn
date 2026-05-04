# CONFIG_RECEIPT_PATTERNS.md

> Spec input for Saturn-qj5.15 (per-turn UI receipt) and qj5.13 (admin Configure page).
> Question: how do other tools show "applied" config vs "configured" config?

## Why this matters for Saturn

Saturn lets a publisher advertise a model endpoint over mDNS/DNS-SD, with TXT-record overrides for `model`, `temperature`, `max_tokens`, `system_prompt`, etc. A user sets `max_tokens=50` in the Configure page or via TXT — but did the upstream LLM actually honor it? Today's UI shows the *configured* value; if the server silently substitutes a different model, ignores `max_tokens`, or routes to a fallback provider, the user has no way to see the truth. The per-turn receipt closes that trust loop: every assistant message must carry a small, honest accounting of what the server actually applied for *that* turn.

## Sources canvassed (ranked by relevance to Saturn)

1. **OpenRouter — Generations API** — https://openrouter.ai/docs/sdks/python/api-reference/generations — Per-generation receipt object: `id`, `provider_name`, `model`, `tokens_prompt`, `tokens_completion`, `total_cost`, `finish_reason`, `streamed`. Closest analog to what Saturn needs.
2. **OpenRouter — Usage Accounting** — https://openrouter.ai/docs/guides/administration/usage-accounting — Inline `usage` block in the streaming response itself; the chat UI surfaces tokens + provider in a chip below each message.
3. **OpenRouter — Provider Routing** — https://openrouter.ai/docs/guides/routing/provider-selection — User configures an `order` array; the response identifies which provider in that order actually served. Pattern: configured-list-vs-resolved-one.
4. **Chrome DevTools — Network panel** — https://developer.chrome.com/docs/devtools/network/reference — Canonical receipt UI: per-request row collapses to a one-line summary, expands to Headers/Payload/Response/Timing tabs. Configured headers (request) shown alongside applied headers (response).
5. **Grafana — Query Inspector** — https://grafana.com/docs/grafana/latest/visualizations/explore/explore-inspector/ — Stats tab shows the actual query the datasource ran (post-templating), execution time, row counts. Distinct from the panel's "configured" query in the editor.
6. **Grafana — Panel Inspector** — https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/panel-inspector/ — Stats / Query / JSON tabs let you compare panel config to what was sent and returned.
7. **Kubernetes — Server-Side Apply / managedFields** — https://kubernetes.io/docs/reference/using-api/server-side-apply/ — `kubectl get -o yaml` returns `spec` (desired) + `status` (observed) + `metadata.managedFields` (who set what). Three-axis honesty.
8. **AWS IAM — Policy Simulator** — https://aws.amazon.com/blogs/security/an-in-depth-look-at-the-iam-policy-simulator/ — "Effective permissions" view: given all attached/inherited/boundary policies, what does the principal *actually* get? Resolved-not-configured.
9. **VS Code — settings.json scope cascade** — https://code.visualstudio.com/docs/configure/settings — Settings UI shows the resolved value with a marker indicating which scope (User/Workspace/Folder) supplied it; clicking jumps to the source.
10. **LM Studio — Load parameters surface** — https://lmstudio.ai/docs/developer/rest/load — Loaded model exposes `flash_attention`, `num_experts`, actual `context_length` — distinct from what was requested at load time (some flags are silently coerced).

## Three distilled patterns Saturn should adopt

### Pattern 1: Inline per-turn footer chip

- **What it is.** A small one-line strip directly under each assistant message: `gpt-4o-mini · t=0.7 · 47/50 tok · stop:length`. Always visible, never modal. Hover or click expands to a full receipt drawer (Pattern 2).
- **Where observed.** OpenRouter chat UI (model + provider + token chip under every reply); Chrome DevTools Network row (one-line summary per request).
- **Saturn application.** Render below every assistant turn: `model · temp · used/cap tokens · provider · [overrides applied: 2]`. Color the token count amber when `used == cap` (capacity hit — output may be truncated). Show a small `Δ` icon if the applied model differs from the publisher-advertised default.
- **Implementation cost.** Low. Server already knows resolved config; add a `meta` object to the per-turn response payload (`model`, `temperature`, `max_tokens_cap`, `tokens_used`, `finish_reason`, `provider`, `overrides_applied[]`). Brutus wires a `<TurnReceipt>` component into the existing message renderer.

### Pattern 2: Expandable receipt drawer

- **What it is.** Clicking the footer chip slides open a panel showing the full resolved-config object next to the *configured* one, diff-highlighted. Mirrors DevTools' Headers tab (Request vs Response) and `kubectl get -o yaml` (spec vs status).
- **Where observed.** Chrome DevTools Network → Headers tab; Grafana Query Inspector → Query tab; `kubectl get pod -o yaml`.
- **Saturn application.** Two columns: **Configured** (what the publisher's TXT records / admin Configure page declared) vs **Applied** (what the server used for this turn). Green check where they match, amber `≠` where they diverge, red `✗` where the server ignored an override entirely. Include a "copy as JSON" button.
- **Implementation cost.** Medium. Requires the server to return both the pre-resolution config and the post-resolution config in the receipt payload — plumbing through the resolver layer. Brutus needs a diff renderer (already trivial with a small util).

### Pattern 3: Provenance marker (which scope set this?)

- **What it is.** For each field in the receipt, show *where the value came from*: TXT record, admin Configure page, server default, or upstream coercion. Like VS Code's "this setting is from your Workspace" annotation, or Kubernetes `managedFields`.
- **Where observed.** VS Code settings UI (scope indicator + jump-to-source); Kubernetes `managedFields`; AWS IAM "this permission granted by policy X".
- **Saturn application.** In the expanded drawer, each row gets a tiny badge: `[TXT]`, `[Configure]`, `[default]`, `[upstream-coerced]`. The last is the critical one — it's how Saturn admits "you asked for `temperature=2.0` but the upstream provider clamped it to 1.0". Click badge → highlight that source in the Configure page (qj5.13) when reachable.
- **Implementation cost.** High. Requires the resolver to emit a per-field provenance record, not just a final value. But this is the highest-trust pattern — it's the difference between "trust me" and "show me the work".

## Recommendation for Saturn-qj5.15

**Primary: Pattern 1 (inline footer chip) + drawer-on-click into Pattern 2.** This matches user expectation set by OpenRouter's chat UI and DevTools' Network panel — the two reference experiences for "per-event receipt." Ship Pattern 3 (provenance badges) as a follow-up inside the drawer once the resolver emits provenance metadata; do not block qj5.15 on it.

**Required fields in the receipt (must show, every turn):**
- `model` — actual model ID the upstream returned (not the requested alias)
- `temperature` — value applied (with note if upstream coerced)
- `max_tokens` — cap **and** tokens actually generated, with hit/not-hit indicator (amber when `used == cap`)
- `system_prompt` — first ~120 chars + expand-to-full; show hash so user can verify against Configure
- `provider` / `upstream` — which endpoint was actually contacted (host, ideally with mDNS service name)
- `overrides_applied[]` — list of TXT-record or Configure-page values that won over server defaults this turn
- `finish_reason` — `stop` / `length` / `content_filter` / `tool_use`

**Hard-to-surface honestly (call out in the drawer with a "best-effort" caveat):**
- `stop_sequences` — server can't always prove the upstream honored them without re-tokenizing
- `top_p` / `top_k` — many providers silently ignore; mark as "requested, not verifiable"
- Tool-call schemas — only verifiable post-hoc by inspecting which tools the model invoked

## Anti-patterns to avoid

- **Showing CONFIGURED instead of APPLIED.** The bug we exist to prevent. If the server can't prove a value was applied, label it "requested" and gray it out — never let configured values masquerade as receipts.
- **Receipt UI on a separate page.** Kills the trust loop. The whole point is "I just got this answer; is it the answer I asked for?" — answer must be one glance away, not one navigation away. (AWS IAM's effective-permissions view fails here: it's three clicks deep.)
- **Walls of JSON in the chat.** Vercel's deployment-detail dumps are an example — the data is right but the surface is hostile. Use the chip+drawer pattern; reserve raw JSON for a "copy" button.
- **Silent fallback without a marker.** If TXT said `model=llama-70b` and the server fell back to `llama-8b`, that MUST be visually distinct (the `Δ` icon, an amber row). Silent substitution is worse than no override system at all.
- **One global receipt for the whole session.** Per-turn config can vary (TXT records can change between mDNS announcements; admin can edit Configure mid-session). Receipt must be scoped to the turn it describes.
