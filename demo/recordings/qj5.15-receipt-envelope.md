# qj5.15 — saturn_meta envelope: Configured vs Applied

*2026-05-05T02:26:44Z by Showboat 0.6.1*
<!-- showboat-id: 1bd39091-8f2a-435b-8eac-9821a203f73f -->

**Status: shipped (commit 3de812c).** Per gullivan's CONFIG_RECEIPT_PATTERNS.md, every assistant turn now carries a `saturn_meta` envelope as the final SSE chunk before `data: [DONE]`. Six invariants pin the honesty contract: applied values are read from the upstream's response (never echoed from the request), `system_prompt` is fingerprinted not inlined, every turn is independent, `schema_version` is pinned at 1, and unverifiable params (`top_p`, `stop`) are explicitly labelled. Test surface `saturn/tests/test_receipt_meta.py` reads 6/6 GREEN (+ 1 SKIPPED without OPENROUTER_PROVISIONING_KEY) per hardener transcript.

## The user-trust angle

Pattern 1 (footer chip) + Pattern 2 (expandable Configured-vs-Applied drawer) let the user see what the upstream actually applied to their turn — not what they asked for. `max_tokens=50` finished at 47? Receipt says `finish_reason=stop`. Finished at 50? `finish_reason=length`. Different model than requested? `diff.coerced: ['model']`. The envelope is the screen; this scaffold renders the same data as a textual two-column for showboat-friendly capture.

## Reproducer — POSTs /api/chat (stream:true), parses SSE, renders the diff

Spawns `saturn web` with isolated SATURN_DATA_DIR + SATURN_SERVICES_DIR (same fixture shape as saturn/tests/test_receipt_meta.py), drops a default-runner Ollama probe, POSTs a deterministic prompt with max_tokens=50, temperature=0, top_p=0.01, and a fingerprintable system message. Captures the last 600 bytes of the SSE stream + the saturn_meta payload + a Pattern-1+2 two-column diff.

```bash
bash demo/recordings/qj5.15_receipt_probe.sh
```

```output
=== /api/chat stream → tail (last 600 chars) ===
":{"prompt_tokens":32,"completion_tokens":4,"total_tokens":36}}

data: {"saturn_meta": {"schema_version": 1, "configured": {"model": "qwen2.5:0.5b", "temperature": 0.0, "max_tokens": 50, "top_p": 0.01}, "applied": {"max_tokens": 50, "model": "qwen2.5:0.5b", "finish_reason": "stop", "usage": {"prompt_tokens": 32, "completion_tokens": 4, "total_tokens": 36}, "system_prompt_sha256": "cc669131dc1c991c6ae61360ae74599316f2e9aeef5d6a429f0cd21b7f96dc98", "system_prompt_preview": "You are a determ\u2026"}, "verifiability": {"top_p": "requested-not-verifiable"}, "diff": {"coerced": []}}}

data: [DONE]



=== saturn_meta envelope ===
{
  "schema_version": 1,
  "configured": {
    "model": "qwen2.5:0.5b",
    "temperature": 0.0,
    "max_tokens": 50,
    "top_p": 0.01
  },
  "applied": {
    "max_tokens": 50,
    "model": "qwen2.5:0.5b",
    "finish_reason": "stop",
    "usage": {
      "prompt_tokens": 32,
      "completion_tokens": 4,
      "total_tokens": 36
    },
    "system_prompt_sha256": "cc669131dc1c991c6ae61360ae74599316f2e9aeef5d6a429f0cd21b7f96dc98",
    "system_prompt_preview": "You are a determ\u2026"
  },
  "verifiability": {
    "top_p": "requested-not-verifiable"
  },
  "diff": {
    "coerced": []
  }
}

=== Configured vs Applied (gullivan Pattern 1+2) ===

  field            configured                       applied                         
  ---------------- -------------------------------- --------------------------------
  model            qwen2.5:0.5b                     qwen2.5:0.5b                    
  max_tokens       50                               50                              
  temperature      0.0                              —                               
  top_p            0.01                             —                               
  system_prompt    <inline>                         cc669131dc1c991c…               
  finish_reason    —                                stop                            
```

## Reading the live envelope

- **schema_version=1** — pinned per §17.C.4.5; future-versioning hook.

- **applied.max_tokens=50** matches `configured.max_tokens=50` — but more importantly, `applied.usage.completion_tokens=4` ≤ 50 with `applied.finish_reason=stop` (model finished early; cap was honoured but not hit). The receipt reads the upstream's own response — not echoed from the request body — so a misbehaving upstream that ignored `max_tokens` would surface here.

- **applied.model=qwen2.5:0.5b** matches the request; if the upstream had silently substituted, `diff.coerced` would carry the field name.

- **applied.system_prompt_sha256** is the SHA-256 of the secret system message; the full prompt is NOT in the envelope (preview is ≤ 16 chars + ellipsis: `"You are a determ…"`). §17.C.4.3 honoured.

- **verifiability.top_p="requested-not-verifiable"** — Saturn forwarded `top_p=0.01` but the upstream doesn't echo it back, so the receipt is honest about that. §17.C.4.6 honoured.

- **diff.coerced=[]** — nothing was silently substituted on this turn.

## Verifying drift

    bash demo/recordings/qj5.15_receipt_probe.sh

    uvx showboat verify demo/recordings/qj5.15-receipt-envelope.md  # diff

Drift gates from this snapshot: any future regression where a chunk before `[DONE]` lacks `saturn_meta`, where `schema_version` flips, where `system_prompt_sha256` is replaced by the literal prompt text, or where `verifiability.top_p` reverts to a numeric value (vs the labelled string) surfaces as a non-zero verify exit.

## UI Pattern 1 + Pattern 2 — pending

Server-side ships here. The `Web-UI/app.js` chip + drawer rendering of `saturn_meta` is gullivan's UI hand-off; once it lands, capture via Playwright (the harness's `tests.harness.web.serve()` + `add_init_script` + `page.route` patterns from Saturn-7j3 apply directly). Save under demo/recordings/qj5.15-chip.png + qj5.15-drawer.png and append via `uvx showboat image`.

## Implementation pointers

- Spec: `CONFIG_RECEIPT_PATTERNS.md` (gullivan; Patterns 1, 2, 3).

- Test surface: `saturn/tests/test_receipt_meta.py` (7 tests; 6 GREEN on Ollama; 1 SKIPPED without OPENROUTER_PROVISIONING_KEY for the silent-substitution coercion test).

- Server impl: `saturn/receipt.py` (new) + `saturn/web.py:chat()` synthesises and emits the envelope as the final SSE chunk; runner `/v1/chat/completions` shares the same helper per §17.C.6 step 2.
