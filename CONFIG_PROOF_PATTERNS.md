# CONFIG_PROOF_PATTERNS.md
> Spec input for Saturn-qj5.14 (config-proof test contract). Brutus folds this into CONTRACT.md.
> Question: how do real-world LLM test suites assert that a config knob was actually honored?

## Per-knob assertion patterns

### 1. max_tokens enforcement
**Pattern:** Assert both `usage.completion_tokens == N` AND `finish_reason == "length"`. The dual check distinguishes "model stopped naturally under cap" from "cap actually clamped."
```python
# vllm tests/entrypoints/openai/completion/test_completion.py — test_single_completion
assert len(choice.text) >= 5
assert choice.finish_reason == "length"
assert completion.usage == openai.types.CompletionUsage(
    completion_tokens=5, prompt_tokens=6, total_tokens=11
)
```
- Source: https://github.com/vllm-project/vllm/blob/main/tests/entrypoints/openai/completion/test_completion.py
- Notes: vLLM exact-equality on `CompletionUsage` only works because the test prompt + max_tokens make finish-by-length deterministic. For Saturn, prefer `<=` on completion_tokens (allows EOS-before-cap) plus `or finish_reason == "length"` disjunction.

### 2. temperature=0 determinism
**Pattern:** Run N>=2 calls with identical prompt+seed, assert outputs equal (or assert single unique value across many runs).
```python
# Dylan Castillo, "Controlling randomness in LLMs"
tokens = []
for i in range(100):
    token = generate_text("Tell me a joke about dogs",
                         temperature=1, seed=42)
    tokens.append(token)
assert len(set(tokens)) == 1
```
- Source: https://dylancastillo.co/posts/seed-temperature-llms.html
- Notes: Hard caveat — even temp=0 + seed is NOT byte-equal across batch sizes (vLLM continuous batching), GPU kernels, or quietly-rolled provider model versions. OpenAI exposes `system_fingerprint`; Saturn should record it and only assert determinism *within* a fingerprint window. For local Ollama, determinism holds if `num_batch` and model file hash are pinned.

### 3. model selection verification
**Pattern:** Parametrize over models; assert `response.model` equals requested model OR matches a registered alias.
```python
# litellm tests/local_testing/test_completion.py
@pytest.mark.parametrize("model", ["gpt-3.5-turbo", "gpt-4", "gpt-4o"])
def test_completion_openai_params(model):
    response = completion(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
    )
```
- Source: https://github.com/BerriAI/litellm/blob/main/tests/local_testing/test_completion.py
- Notes: LiteLLM only tests the call goes through; for proof of *which* model served, also `assert response.model.startswith(requested)` — providers sometimes return canonical names (`gpt-4-0613` for `gpt-4`). Saturn should accept prefix-match.

### 4. system prompt influence
**Pattern:** Positive-control marker. System prompt instructs "always include token <MARKER>"; assert marker appears in output.
```yaml
# promptfoo — contains assertion (canonical pattern)
tests:
  - vars:
      input: "say hi"
    assert:
      - type: contains
        value: "PIRATE_MARKER_42"   # planted in system prompt: "Always end with PIRATE_MARKER_42"
```
- Source: https://www.promptfoo.dev/docs/configuration/expected-outputs/
- Notes: Some providers silently drop system messages on certain models (older Mistral, some Ollama templates). Saturn must use a marker the model would NEVER emit unprompted (random nonce, not "pirate"). Negative control: same prompt without system message must fail the contains check.

### 5. stop sequences
**Pattern:** Assert output does NOT contain the stop string AND `finish_reason == "stop"`. Some APIs strip the stop token, some leave it; test both.
```python
# Pattern composed from vLLM completion test conventions
resp = client.completions.create(
    model=m, prompt="Count: 1, 2, 3,", max_tokens=50, stop=["5"]
)
assert "5" not in resp.choices[0].text
assert resp.choices[0].finish_reason == "stop"
```
- Source: https://github.com/vllm-project/vllm/blob/main/tests/entrypoints/openai/completion/test_completion.py (finish_reason convention)
- Notes: Ollama's OpenAI-compat endpoint returns `finish_reason="stop"` for both EOS and stop-string hits — disambiguate by checking stop-string is the suffix of pre-trimmed text, OR by setting a *unique* stop sequence and asserting the output ends just before it.

### 6. top_p / top_k (statistical)
**Pattern:** Single-shot is unobservable. Sample N>=50 with fixed seed-per-call disabled; compare token-distribution to baseline (chi-square) OR assert `len(set(outputs)) <= K` for top_k.
```python
# Composed pattern (no canonical OSS test exists for this — promptfoo/vllm both punt)
samples = [client.completions.create(model=m, prompt=p, top_k=1,
            temperature=1.0, max_tokens=1).choices[0].text for _ in range(50)]
assert len(set(samples)) == 1   # top_k=1 must collapse to argmax
```
- Source: derived; closest real example is vLLM `tests/samplers/` which tests sampler internals not API surface.
- Notes: This is the shakiest knob to prove externally. For top_p=0.1 vs 0.9 you need a KS test on token-rank distributions — too expensive for CI. Saturn pragmatic plan: assert top_k=1 collapses (single token), assert top_p=0 collapses; treat intermediate values as forwarded-not-honored (unit-test the wire payload).

## Three pitfalls Saturn must handle
1. **Ollama `max_tokens` vs `num_predict` silent drop** — Ollama's native `/api/chat` and `/api/generate` reject `max_tokens` (logs `"invalid option provided" option=max_tokens`); only `/v1/chat/completions` aliases it. Saturn must (a) normalize at the proxy layer and (b) include a regression test that sends `max_tokens=5` to the native endpoint and asserts completion_tokens<=5 — this currently silently produces unbounded output. Ref: https://github.com/ollama/ollama/issues/12779
2. **temperature=0 is not byte-deterministic across batch sizes** — vLLM continuous batching, GPU non-determinism, and quiet provider model rolls all break naive equality. Use OpenAI's `system_fingerprint` (or local model file SHA) as the determinism epoch; only assert byte-equal within a window.
3. **System prompt silently dropped** — Some provider/model combos collapse system into user, or ignore it entirely. Always pair the influence test with a *negative control* (same call, no system) that must produce a different output — otherwise a passing test could mean "system worked" OR "model is just verbose."

## Sources canvassed
1. vLLM completion tests — https://github.com/vllm-project/vllm/blob/main/tests/entrypoints/openai/completion/test_completion.py — gold standard for `finish_reason` + `usage.completion_tokens` dual-assert.
2. LiteLLM completion tests — https://github.com/BerriAI/litellm/blob/main/tests/local_testing/test_completion.py — parametrized model coverage; weak on response.model verification.
3. promptfoo deterministic assertions — https://www.promptfoo.dev/docs/configuration/expected-outputs/deterministic/ — canonical taxonomy: equals/contains/regex/icontains/contains-all/is-json + cost+latency thresholds.
4. promptfoo assertion catalog — https://www.promptfoo.dev/docs/configuration/expected-outputs/ — full set including `not-contains` (good for stop-sequence proof) and `python`/`javascript` custom assertions.
5. Dylan Castillo, seed/temperature determinism — https://dylancastillo.co/posts/seed-temperature-llms.html — clearest `assert len(set(tokens)) == 1` pattern + system_fingerprint caveat.
6. Ollama issue #12779 — https://github.com/ollama/ollama/issues/12779 — the max_tokens/num_predict silent-drop bug; required reading for Saturn's Ollama backend tests.
7. Ollama issue #15783 — https://github.com/ollama/ollama/issues/15783 — Go sampler silently ignores `repeat_penalty`/`frequency_penalty`/`presence_penalty`; same class of bug, same test pattern needed.
8. open-webui #18618 — https://github.com/open-webui/open-webui/issues/18618 — root-level `max_tokens` dropped instead of converted; real-world example of the regression Saturn's contract must catch.
9. llama.cpp server README — https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md — confirms `n_predict` naming convention divergence from OpenAI `max_tokens`.
10. LangChain standard tests — https://docs.langchain.com/oss/python/contributing/standard-tests-langchain — provider-conformance test framework pattern (cross-provider invariants), matches Saturn's TXT-record→assertion matrix shape.

## Recommendation for qj5.14 CONTRACT.md
Adopt vLLM's dual-assertion pattern (`completion_tokens` numeric bound + `finish_reason` enum) as the contract template for every numeric knob, and promptfoo's `contains` + negative-control pair for every prompt-shape knob. Split the test matrix two ways: (a) **forwarding** tests (knob X in TXT record → knob X on upstream wire payload) are pure unit tests at the Saturn server layer, fast and cheap; (b) **honoring** tests (model actually obeys X) require a real backend — pin local Ollama with a fixed model SHA as the cheap integration target, and accept that top_p/top_k honoring is best-effort statistical (collapse-at-extremes only) rather than per-call provable.
