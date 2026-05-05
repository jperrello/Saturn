# Saturn-8ve — settings rewrite live-diff

## Contract

Per RUN_MAY05_CONTEXT.md: settings panel exposes 11 OWUI-style params
(temperature, top_p, top_k, max_tokens, system_prompt, frequency_penalty,
presence_penalty, repeat_penalty, min_p, seed, stop). Each param must
demonstrably affect Saturn responses via live diff before shipping.

Pattern (gullivan note): pin seed N, send identical prompt twice,
vary one param between calls, assert outputs differ.

## Status

**RED — partial pass.** Seed determinism + 7 of 10 params verified.
**3 params fail** the live-diff:
- `top_k` — identical output for top_k=1 vs top_k=100 (seed=42)
- `repeat_penalty` — identical for 1.0 vs 2.0
- `min_p` — identical for 0.0 vs 0.9

## Verification

- Scenario: `tests/bombadil/settings_8ve.py`
- Run: `python3 tests/bombadil/settings_8ve.py`
- Result: 1/2 oracles green; 8/11 individual params + seed self-test green.
- Artifacts: `tests/bombadil/results/settings_8ve/result.json`.
- Real Web-UI on a live ephemeral port. Real Ollama qwen2.5:0.5b at
  127.0.0.1:11434 via Saturn `/api/chat` against an `api_type=ollama`
  service.
- No mocks. 25 live model calls.

### Per-param results (seed=42, prompt fixed, baseline temp=0.8 top_p=0.9 top_k=40 max_tokens=50)

| Param | Variant A → B | Differ? |
|-------|---------------|---------|
| seed self-test (same seed twice) | seed=42 vs seed=42 | identical ✓ |
| seed self-test (diff seeds) | seed=42 vs seed=999 | differ ✓ |
| temperature | 0.0 vs 1.5 | ✓ |
| top_p | 0.1 vs 1.0 | ✓ |
| top_k | 1 vs 100 | **✗** |
| max_tokens | 8 vs 80 | ✓ |
| system_prompt | "single word" vs "three sentences in French" | ✓ |
| frequency_penalty | 0.0 vs 2.0 | ✓ |
| presence_penalty | 0.0 vs 2.0 | ✓ |
| repeat_penalty | 1.0 vs 2.0 | **✗** |
| min_p | 0.0 vs 0.9 | **✗** |
| stop | (none) vs ["the","a"," "] | ✓ |

### Hypothesis on cause

`/api/chat` resolves to `{base_url}/chat/completions`, i.e. Ollama's
OpenAI-compat endpoint. That endpoint silently drops Ollama-native
sampling params (`top_k`, `repeat_penalty`, `min_p`, `repeat_last_n`,
mirostat*, num_ctx, etc.). The OPENAI/OLLAMA allowlists in
`saturn/web.py` permit them client-side, but they never reach the
sampler.

Suggested fix for hardener: when `api_type=ollama`, either
(a) route through Ollama's native `/api/chat` with the params nested
under `options`, or (b) wrap the dropped params in OpenAI-compat
`extra_body`/`options` for forwarding.

## Follow-up beads

- **Saturn-kpf** — top_k not honored via /api/chat
- **Saturn-vz6** — repeat_penalty not honored via /api/chat
- **Saturn-zy5** — min_p not honored via /api/chat

All three filed P1, owner-pending hardener. Saturn-8ve **stays open**
until the three follow-ups close and live-diff comes back fully green.

Status: **RED / 8 of 11 params verified — Saturn-8ve.**
