# qj5.15 — saturn_meta envelope: Configured vs Applied

*2026-05-04T22:20:05Z by Showboat 0.6.1*
<!-- showboat-id: f4145d2b-c801-45d3-9421-33f4d7c30cbf -->

**Status: scaffold prefetched, awaiting receipt.py + _emit_meta.** Per gullivan's CONFIG_RECEIPT_PATTERNS.md, every assistant turn must carry a `saturn_meta` envelope as the final SSE chunk before `data: [DONE]` (or as a sibling key when `stream: false`). Six invariants pin the honesty contract: applied values are read from the upstream's response (never echoed from the request), `system_prompt` is fingerprinted not inlined, every turn is independent, schema_version is pinned, and unverifiable params (top_p, stop) are explicitly labelled.

## The user-trust angle

Pattern 1 (footer chip) + Pattern 2 (expandable Configured-vs-Applied drawer) let the user see what the upstream actually applied to their turn — not what they asked for. `max_tokens=50` finished at 47? Receipt says `finish_reason=stop`. Finished at 50? `finish_reason=length`. Different model than requested? `diff.coerced: ['model']`. The envelope is the screen; this scaffold renders the same data as a textual two-column for showboat-friendly capture.

## Reproducer — POSTs /api/chat (stream:true), parses SSE, renders the diff

Spawns `saturn web` with isolated SATURN_DATA_DIR + SATURN_SERVICES_DIR (same fixture shape as saturn/tests/test_receipt_meta.py), drops a default-runner Ollama probe, POSTs a deterministic prompt with max_tokens=50, temperature=0, top_p=0.01, and a fingerprintable system message. Captures the last 600 bytes of the SSE stream + the saturn_meta payload + a Pattern-1+2 two-column diff.

```bash
bash demo/recordings/qj5.15_receipt_probe.sh
```

```output
=== /api/chat stream → tail (last 600 chars) ===
qwen2.5:0.5b","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"."},"finish_reason":null}]}

data: {"id":"chatcmpl-953","object":"chat.completion.chunk","created":1777933209,"model":"qwen2.5:0.5b","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":"stop"}]}

data: {"id":"chatcmpl-953","object":"chat.completion.chunk","created":1777933209,"model":"qwen2.5:0.5b","system_fingerprint":"fp_ollama","choices":[],"usage":{"prompt_tokens":32,"completion_tokens":4,"total_tokens":36}}

data: [DONE]



=== saturn_meta envelope ===
  (absent — receipt envelope not yet wired; qj5.15 implementation pending)

=== Configured vs Applied (gullivan Pattern 1+2) ===

  field            configured                       applied                         
  ---------------- -------------------------------- --------------------------------
  model            qwen2.5:0.5b                     —                               
  max_tokens       50                               —                               
  temperature      0.0                              —                               
  top_p            0.01                             —                               
  system_prompt    <inline>                         —                               
  finish_reason    —                                —                               
```

## Reading the output today

The SSE stream's final usable chunk is the upstream's `usage` block — no `saturn_meta` follows. The Applied column is empty everywhere. **That is the gap qj5.15 closes.** Once `saturn/receipt.py` lands and `saturn/web.py:chat()` calls `_emit_meta` against the buffered final usage chunk, rerunning this script will populate every Applied cell from the upstream's own response — and `finish_reason`, `model`, `system_prompt_sha256` will all read true.

## Verifying drift

    bash demo/recordings/qj5.15_receipt_probe.sh

    uvx showboat verify demo/recordings/qj5.15-receipt-envelope.md  # diff against this snapshot

Once the envelope ships, the verify diff *is* the artifact: every Applied cell flips from `—` to a real upstream-read value.

## UI Pattern 1 + Pattern 2 — when the chip + drawer ship in Web-UI/app.js

After server-side ships and gullivan's UI work follows, capture the chip and the expanded drawer via Playwright (model the harness already has via tests.harness.web.serve()). Save under demo/recordings/qj5.15-chip.png + qj5.15-drawer.png and append via `uvx showboat image`.

## Implementation pointers

- Spec: `CONFIG_RECEIPT_PATTERNS.md` (gullivan; Patterns 1, 2, 3).

- Test surface: `saturn/tests/test_receipt_meta.py` (7 tests; 6 RED today on Ollama; 1 SKIPPED without OPENROUTER_PROVISIONING_KEY).

- Implementer landing zone: `saturn/receipt.py` (new) + `saturn/web.py:chat()` calling it; runner `/v1/chat/completions` shares the same helper per §17.C.6 step 2.

- Envelope shape: `{schema_version: 1, applied: {...read from upstream}, diff: {coerced: [...]}, verifiability: {top_p: 'requested-not-verifiable', ...}}`.
