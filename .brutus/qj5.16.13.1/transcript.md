# qj5.16.13.1 _resolve TrustRebindError 403 — red phase

*2026-05-04T21:18:02Z by Showboat 0.6.1*
<!-- showboat-id: bce33215-e15c-4458-a4a6-25b63653c6e3 -->

Spec: SECURITY_AUDIT.md §15.3. saturn/web.py:_resolve must check known_nodes.load()['rejected'] when service not in _discovered AND no live config; if a rejection is recorded for that name, raise HTTPException(403, detail={error: trust_rebind_rejected, service, expected_prefix[8], seen_prefix[8], seen_host, remediation}). Today produces a generic 404 indistinguishable from a stopped service — frontend banner cannot render against it.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_resolve_trust_rebind.py --timeout=30 -v 2>&1 | tail -10
```

```output
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_resolve_trust_rebind.py::test_resolve_raises_403_when_rejection_recorded
FAILED saturn/tests/test_resolve_trust_rebind.py::test_resolve_403_takes_precedence_over_404
==================== 2 failed, 1 passed, 1 warning in 2.21s ====================
```
