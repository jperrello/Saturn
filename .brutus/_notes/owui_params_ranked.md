# OWUI / OpenAI-compatible params — RANKED PASS

Successor to `owui_params_rough.md`. Ships the scoring grid, Saturn-specific
defaults, and the Ollama-vs-OpenRouter naming divergence sheet that hardener
+ bombadil need to wire up Saturn-8ve.

Scoring rubric — each axis 1–5, score = product (max 125). One axis at 1 zeroes
it out by intent.

- **I — user-visible impact**: Will a non-power user *see* the difference in a
  single prompt? 5 = obviously different output. 1 = telemetry-only.
- **P — cross-backend portability**: How many of {OpenAI, vLLM,
  llama.cpp/Ollama, OpenRouter} accept it without backend-specific glue?
  5 = all four native. 3 = passthrough via `extra_body` everywhere. 1 = one
  backend only.
- **D — not-already-defaulted-fine**: How often does the stock value bite a
  real user? 5 = stock is wrong/limiting for common cases. 1 = stock is
  basically always right.

Saturn baseline already exposed in `saturn-8ve` scope: `temperature`, `top_p`,
`top_k`, `max_tokens`, `system_prompt`. (Today's `runner.py` only forwards
`temperature` / `max_tokens` / `tools` / `tool_choice` — `top_p` / `top_k` are
Saturn-8ve additions, not legacy.)

## Tier S — ship in the first cut

| # | Param | I | P | D | Score | Saturn default | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `seed` | 5 | 5 | 5 | **125** | unset (best-effort upstream) | Ship FIRST. Bombadil's live-diff harness needs it pinned to make penalty diffs deterministic. OpenAI/vLLM/llama.cpp/Ollama/OpenRouter all accept. |
| 2 | `frequency_penalty` | 5 | 5 | 4 | **100** | `0.0` | Native everywhere. Visible at `>=1.0` on repetitive prompts. |
| 3 | `presence_penalty` | 4 | 5 | 4 | **80** | `0.0` | Native everywhere. Topic-drift effect. |
| 4 | `stop` | 5 | 5 | 3 | **75** | `[]` | Universal. Truncation diff is bulletproof for harness. |
| 5 | `repetition_penalty` | 5 | 3 | 5 | **75** | unset | Stronger than `frequency_penalty` but **NOT in OpenAI spec** — must go through `extra_body` for vLLM/OpenRouter; native for Ollama/llama.cpp. Saturn's proxy must whitelist it through. |
| 6 | `min_p` | 4 | 3 | 4 | **48** | unset | Modern alternative to `top_p`. vLLM accepts via `extra_body`; native on Ollama/llama.cpp; OpenRouter passthrough. **Not** OpenAI native. |

## Tier A — ship in the second cut (real impact, UX or portability caveats)

| # | Param | I | P | D | Score | Saturn default | Notes |
|---|---|---|---|---|---|---|---|
| 7  | `response_format` | 5 | 4 | 4 | **80** | `{"type":"text"}` | OpenAI/vLLM/OpenRouter native; llama.cpp via grammar. JSON-mode toggle is a binary, very visible diff — but UI needs to surface "schema vs object" choice. |
| 8  | `logit_bias` | 4 | 4 | 3 | **48** | `{}` | Power-user. OpenAI/vLLM/llama.cpp native; OpenRouter partial. UI cost is real (token-id picker). |
| 9  | `n` | 4 | 4 | 1 | **16** | `1` | Default-is-fine for chat UI. Skip unless Saturn surfaces a multi-pane "alternatives" view. |
| 10 | `logprobs` / `top_logprobs` | 2 | 4 | 1 | **8** | unset | Telemetry, not output. Skip for end-user panel; expose only if Saturn ships a "confidence" overlay. |
| 11 | `user` | 1 | 5 | 1 | **5** | unset | No live-diff. **Skip.** |

## Tier B — backend-specific, gated on backend detection

These only fire on llama.cpp / Ollama. If Saturn detects a non-llama backend it
must hide them or grey them out — sending them to vLLM/OpenAI is at best
ignored, at worst a 400.

| # | Param | I | P | D | Score | Saturn default | Notes |
|---|---|---|---|---|---|---|---|
| 12 | `mirostat` (+ `mirostat_tau`, `mirostat_eta`) | 4 | 1 | 4 | **16** | `0` (off) | Mode flip — when on, disables `top_k`/`top_p`. UI must communicate this or it confuses users. |
| 13 | `typical_p` | 3 | 1 | 3 | **9** | `1.0` | llama.cpp/Ollama/HF only. |
| 14 | `tfs_z` (tail-free sampling) | 2 | 1 | 2 | **4** | `1.0` | Diminishing returns vs `min_p`. **Skip.** |
| 15 | `dynatemp_range` / `dynatemp_exponent` | 3 | 1 | 3 | **9** | `0.0` / `1.0` | Niche; pair only. |
| 16 | `repeat_last_n` (Ollama) / `repetition_penalty_range` (llama.cpp) | 3 | 1 | 3 | **9** | `64` | Companion to `repetition_penalty`. **Naming divergence — see table below.** |
| 17 | `num_ctx` (Ollama) / `truncate_prompt_tokens` (vLLM) | 3 | 2 | 3 | **18** | upstream default | Admin/config concern. Surface in advanced panel only. |

## Tier C — don't expose

`stream` (UX), `tools` / `tool_choice` (separate surface), `service_tier`
(billing), `parallel_tool_calls` (gated on tools), `store` / `metadata`
(audit), `prompt_logprobs` / `echo` / `suffix` (debug), `best_of` (latency
hazard), `length_penalty` / `min_length` (beam-search), `no_repeat_ngram_size`
(blunt; can wreck output), `encoder_repetition_penalty` (text-gen-webui only),
`stream_options.include_usage` (telemetry), `num_predict` (Ollama alias for
`max_tokens` — Saturn must rename, not surface).

## Saturn-specific defaults (canonical table)

What the Saturn UI should preload for a fresh chat. Choose values that match
upstream stock so an unconfigured user sees identical behavior to today.

| Param | Saturn default | Reason |
|---|---|---|
| `temperature` | `1.0` | OpenAI/vLLM stock. Saturn-8ve already reuses. |
| `top_p` | `1.0` | Stock. |
| `top_k` | `0` (disabled) on OpenAI-style; `40` on Ollama-direct | Backend split — OpenAI ignores, Ollama defaults to `40`. |
| `max_tokens` | unset (server decides) | Saturn already passes through only when set. |
| `system_prompt` | empty | Existing. |
| `seed` | unset; UI exposes "🎲 random / 🔒 pin" toggle | Pin button writes a stable int; harness reads it for live-diff. |
| `frequency_penalty` | `0.0` | OpenAI stock. |
| `presence_penalty` | `0.0` | OpenAI stock. |
| `stop` | `[]` | Stock. |
| `repetition_penalty` | unset (sentinel ⇒ omit from payload) | If user explicitly sets, Saturn forwards via `extra_body` for vLLM/OpenRouter and as a top-level field for Ollama/llama.cpp. **Don't default to 1.0** — sending `1.0` to OpenAI proper will 400. |
| `min_p` | unset (sentinel) | Same omit-when-unset rule as repetition_penalty. |
| `response_format` | `{"type":"text"}` | Saturn keeps prose mode unless user picks JSON. |

## Ollama vs OpenRouter (and friends) — naming divergence

The single biggest correctness footgun. Saturn's proxy currently hard-codes
field names to the OpenAI spec; once Tier S/A ship, payload remapping per
backend becomes mandatory.

| User-facing knob | OpenAI / vLLM / OpenRouter | Ollama (`/api/chat`) | llama.cpp `/completion` |
|---|---|---|---|
| max output tokens | `max_tokens` | **`num_predict`** | `n_predict` |
| context window | `truncate_prompt_tokens` (vLLM) / not surfaced (OpenAI) | **`num_ctx`** | `n_ctx` (server-launch only) |
| repeat penalty | `frequency_penalty` (different math!) + `repetition_penalty` (extra_body) | **`repeat_penalty`** | `repeat_penalty` |
| repeat lookback window | `repetition_penalty_range` (vLLM extra_body, llama.cpp) | **`repeat_last_n`** | `repeat_last_n` |
| seed | `seed` | `seed` | `seed` |
| top-k | `top_k` (vLLM extra_body; not OpenAI) | `top_k` | `top_k` |
| stop sequences | `stop` | `stop` | `stop` |
| min-p | `min_p` (extra_body for vLLM/OpenRouter) | `min_p` | `min_p` |
| mirostat trio | n/a | `mirostat` / `mirostat_tau` / `mirostat_eta` | same |

**OpenRouter quirk:** OpenRouter is OpenAI-compatible at the surface, but it
forwards backend-specific fields (`min_p`, `repetition_penalty`, `top_k`,
`mirostat_*`) verbatim to the underlying provider when present. So Saturn
should send them as **top-level fields** to OpenRouter (not nested under
`extra_body`) — OpenRouter does the routing. This differs from vLLM, which
*requires* `extra_body` for non-OpenAI fields.

**Implementation rule for Saturn proxy:**
1. Saturn UI/API speaks one canonical name set (the OpenAI spec where it
   exists, otherwise the most common name — i.e. `repetition_penalty`,
   `min_p`).
2. `runner.py` checks `runner.config.upstream.kind` (already has this
   plumbing) and remaps:
   - kind=`ollama` → rename `max_tokens`→`num_predict`, lift extras to top
     level.
   - kind=`vllm` → keep OpenAI fields top-level; non-OpenAI fields (`min_p`,
     `repetition_penalty`, `top_k` when set) move to `extra_body`.
   - kind=`openrouter` → all fields top-level.
   - kind=`openai` → strip non-spec fields (`min_p`, `repetition_penalty`,
     `top_k`, `mirostat_*`) before send; log a warning.
3. The receipt's `applied` block must record post-rename names so the live
   diff harness compares apples to apples.

## Live-diff verifiability (bombadil-facing)

Each Tier S/A param has a deterministic test recipe:

- **seed**: same seed twice → identical bytes (modulo timestamps in stream
  framing). Different seed → different. Hash compare on content stream.
- **frequency_penalty / presence_penalty**: pin seed; toggle 0.0 → 1.5;
  output bytes must differ. (At 0.0 vs 0.0 they must match.)
- **repetition_penalty**: same recipe.
- **stop**: assert response truncates at first occurrence of any stop string.
- **min_p**: pin seed + high temperature (1.5); toggle 0.0 → 0.1; output
  must differ.
- **response_format=json_object**: `json.loads()` on response content must
  succeed; in `text` mode it may fail.
- **logit_bias**: bias a common token to -100; assert token absent in output.
- **max_tokens**: assert `usage.completion_tokens <= max_tokens`.

Without seed pinning, penalty diffs need N≥5 samples to be statistically
visible — pin seed instead, it's free.

## Sources

- OpenAI Chat Completions reference — https://platform.openai.com/docs/api-reference/chat/create
- vLLM OpenAI-compatible server — https://docs.vllm.ai/en/latest/serving/openai_compatible_server/
- vLLM SamplingParams — https://docs.vllm.ai/en/v0.6.4/dev/sampling_params.html
- Ollama API (Modelfile parameters) — https://github.com/ollama/ollama/blob/main/docs/api.md and https://github.com/ollama/ollama/blob/main/docs/modelfile.md
- llama.cpp server README — https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md
- OpenRouter parameters — https://openrouter.ai/docs/api-reference/parameters
- OWUI chat-params docs — https://docs.openwebui.com/features/chat-conversations/chat-features/chat-params/
- OWUI advanced params discussion — https://github.com/open-webui/open-webui/discussions/3794
- Voxta LLM-params reference — https://doc.voxta.ai/docs/llm-parameters/
- smcleod LLM sampling guide — https://smcleod.net/2025/04/llm-sampling-parameters-guide/
- muxup vendor-recommended params — https://muxup.com/2025q2/recommended-llm-parameter-quick-reference

## Contested / Unclear

- **`repetition_penalty` vs `frequency_penalty` math**: Sources disagree on
  whether they should be exposed together or alternately. smcleod
  recommends `repetition_penalty` only; OpenAI cookbook never mentions
  `repetition_penalty`. Saturn ships both because backends differ on which
  one they actually act on.
- **OpenRouter passthrough behavior**: docs say non-OpenAI fields are
  forwarded, but provider coverage matrix is incomplete — some providers
  silently drop `min_p`. Saturn should log when a field is sent but
  `applied` echo doesn't reflect it.

## Couldn't find

- A definitive list of which OpenRouter providers honor `repetition_penalty`
  vs drop it. Provider-by-provider testing is out of scope here; bombadil's
  live-diff harness will surface drops empirically per upstream.
