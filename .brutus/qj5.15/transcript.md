# qj5.15 saturn_meta receipt envelope — red phase

*2026-05-04T20:50:07Z by Showboat 0.6.1*
<!-- showboat-id: 4091a723-fbed-4c4e-ad4f-408623a2cfd4 -->

Spec: PRE_SPECS_B3.md §17.C + CONFIG_RECEIPT_PATTERNS.md (gullivan). 6 invariants 1:1 with anti-patterns: honest receipt (applied.X from upstream); coerced flagging (diff.coerced); system_prompt fingerprinted (sha256 + ≤120-char preview, never inlined); per-turn independence; schema_version=1; verifiability honesty (top_p=requested-not-verifiable). Receipt rides inline with the chat stream as saturn_meta envelope.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_receipt_meta.py --timeout=120 2>&1 | tail -15
```

```output
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_receipt_meta.py::test_receipt_max_tokens_reflects_actual_completion
FAILED saturn/tests/test_receipt_meta.py::test_receipt_model_echoes_upstream_id
FAILED saturn/tests/test_receipt_meta.py::test_system_prompt_hashed_not_inlined
FAILED saturn/tests/test_receipt_meta.py::test_per_turn_meta_independence - u...
FAILED saturn/tests/test_receipt_meta.py::test_schema_version_present_and_pinned
FAILED saturn/tests/test_receipt_meta.py::test_unverifiable_fields_are_marked
=================== 6 failed, 1 skipped, 1 warning in 16.05s ===================
```
