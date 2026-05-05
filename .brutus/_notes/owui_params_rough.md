# OWUI / OpenAI-compatible params worth exposing — ROUGH PASS

Baseline already in: `temperature`, `top_p`, `top_k`, `max_tokens`, `system_prompt`.

Ranked rough by (visible impact × backend portability × default-isn't-already-fine).
Each entry: param — 1-line rationale + live-diff verifiability hint.

## Tier S — definitely add (high impact, broadly supported, easy live-diff)

1. **frequency_penalty** — OpenAI spec native, vLLM + llama.cpp + Ollama all honor it. At 1.5+ visibly cuts repeated tokens. **Diff:** ask "list synonyms for happy 20 times" — 0.0 vs 1.5 produces clearly different word distributions.
2. **presence_penalty** — OpenAI native, same backends. Pushes model onto new topics. **Diff:** ask for a 200-word paragraph; high presence_penalty changes topic drift visibly.
3. **seed** — OpenAI native (best-effort), vLLM honors strictly, llama.cpp honors. Reproducibility / "regenerate same answer". **Diff:** same seed twice → identical output (greedy-ish); different seed → different. Trivially verifiable.
4. **stop** (stop sequences, list of strings) — OpenAI native, universally supported. Lets users cut at "###" or "</answer>". **Diff:** set stop=["."] → response truncated at first period.
5. **repetition_penalty** — NOT in OpenAI spec but vLLM, llama.cpp, Ollama, OpenRouter all accept it (passthrough via extra_body). Stronger anti-repeat than frequency_penalty. **Diff:** at 1.3 vs 1.0, repeated phrasing collapses.
6. **min_p** — vLLM, llama.cpp, Ollama. Modern alternative to top_p; many practitioners prefer it. **Diff:** min_p=0.1 vs 0.0 visibly tightens distribution at high temp.

## Tier A — probably add (real impact, slight portability or UX caveats)

7. **response_format** (`json_object` / `json_schema`) — OpenAI native, vLLM supports, llama.cpp via grammar. Not all backends accept arbitrary schemas. **Diff:** "give me a name" returns `{"name": "..."}` JSON vs prose. Toggle is binary, very visible.
8. **logit_bias** — OpenAI native, vLLM passes through, llama.cpp supports. Power-user but extremely demonstrable. **Diff:** bias token "the" to -100 → no "the" in output. Possibly too niche for non-power users.
9. **n** (number of completions) — OpenAI native. Trivial visible effect (multiple choices). UX cost: where do you display N answers? Probably skip in chat UI.
10. **logprobs** / **top_logprobs** — OpenAI native, vLLM full support. Returns probability data; "show me confidence". Niche unless Saturn surfaces a UI for it.
11. **user** (string id) — OpenAI accepts but ignored by most; abuse-tracking only. **Skip** — no live-diff possible.

## Tier B — backend-specific, exposure depends on Saturn's typical backend

12. **mirostat** / **mirostat_tau** / **mirostat_eta** — llama.cpp / Ollama only, NOT vLLM/OpenAI. Disables top_k/top_p when active. Good "set perplexity target" knob but mode-flipping behavior is confusing for novices.
13. **typical_p** — llama.cpp/Ollama/HF transformers. Niche but visible.
14. **tfs_z** (tail-free sampling) — llama.cpp/Ollama only. Diminishing returns vs min_p.
15. **dynatemp_range** / **dynatemp_exponent** — llama.cpp dynamic temperature. Niche.
16. **penalty_last_n** / **repetition_penalty_range** — how far back the repeat penalty looks. Useful pairing with repetition_penalty but llama.cpp-only naming.
17. **num_ctx** (Ollama) / `truncate_prompt_tokens` (vLLM) — controls context window. Visible if you push prompt length, but really an admin/config concern, not a per-chat knob.
18. **num_predict** — Ollama alias for max_tokens. Skip (dupe).

## Tier C — skip for end-user panel (admin / niche / no diff)

- **stream** — UX behavior, not a model output knob.
- **tools** / **tool_choice** — feature toggle, not a sampling knob; belongs to a separate UI surface.
- **service_tier** (OpenAI) — billing/latency, no quality diff.
- **parallel_tool_calls** — only matters if tools enabled.
- **store** / **metadata** — admin/audit only.
- **prompt_logprobs** / **echo** / **suffix** — debugging primitives.
- **best_of** — server-side reranking; kills latency, very niche.
- **length_penalty** / **min_length** / **min_tokens** — beam-search-coupled or rarely surfaced; min_tokens occasionally useful for forcing verbose answers.
- **no_repeat_ngram_size** — strong but blunt; can wreck output if misused.
- **encoder_repetition_penalty** — text-gen-webui only, not OpenAI-compat.
- **stream_options.include_usage** — billing telemetry.

## Cross-backend portability cheat-sheet

| Param | OpenAI | vLLM | llama.cpp/Ollama | OpenRouter |
|---|---|---|---|---|
| frequency_penalty | ✅ | ✅ | ✅ | ✅ |
| presence_penalty | ✅ | ✅ | ✅ | ✅ |
| seed | ✅ | ✅ | ✅ | ✅ |
| stop | ✅ | ✅ | ✅ | ✅ |
| repetition_penalty | ❌ | ✅ extra_body | ✅ | ✅ |
| min_p | ❌ | ✅ extra_body | ✅ | ✅ |
| response_format | ✅ | ✅ | partial (grammar) | ✅ |
| logit_bias | ✅ | ✅ | ✅ | partial |
| mirostat_* | ❌ | ❌ | ✅ | partial |
| typical_p / tfs_z | ❌ | partial | ✅ | partial |

## Live-diff caveat (bombadil's mandate)

Every Tier S/A param above CAN be live-diffed deterministically:
- penalties + seed: diffable by holding seed fixed and toggling the penalty (must surface seed input alongside).
- stop: deterministic truncation diff.
- response_format: structural diff (JSON-parse succeeds vs not).
- logit_bias: token presence diff.

**Caveat:** non-seeded penalty diffs at fixed prompt are *probabilistic* — bombadil should pin `seed` during settings-effect tests. Without seed control, frequency/presence diffs need N samples to become statistically obvious.

## Sources (rough)

- OpenAI Chat Completions API ref: https://platform.openai.com/docs/api-reference/chat/create
- vLLM OpenAI-compatible server: https://docs.vllm.ai/en/latest/serving/openai_compatible_server/
- vLLM SamplingParams: https://docs.vllm.ai/en/v0.6.4/dev/sampling_params.html
- llama.cpp server README: linked from cnb.cool mirror
- OWUI chat-params docs: https://docs.openwebui.com/features/chat-conversations/chat-features/chat-params/
- OWUI advanced params discussion: https://github.com/open-webui/open-webui/discussions/3794
- Voxta LLM-params reference (oobabooga lineage): https://doc.voxta.ai/docs/llm-parameters/
- smcleod LLM sampling guide: https://smcleod.net/2025/04/llm-sampling-parameters-guide/
- muxup vendor-recommended params: https://muxup.com/2025q2/recommended-llm-parameter-quick-reference
