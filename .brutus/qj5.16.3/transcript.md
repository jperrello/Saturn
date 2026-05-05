# qj5.16.3 trusted_proxies + XFF rightmost — red phase

*2026-05-04T21:10:05Z by Showboat 0.6.1*
<!-- showboat-id: baa5c758-01ed-422c-a339-9e24936f0385 -->

Spec: SECURITY_AUDIT.md §8 + CONFIG_FIELDS §A.3. Empty trusted_proxies → XFF ignored. Populated + last-hop trusted → rightmost XFF entry is identity. Untrusted peer + XFF → ignored. Invalid CIDR → log warning, skip, don't crash boot. Live-applicable via /api/admin/config without restart. Implementation must pass forwarded_allow_ips=[] to uvicorn to disable its default trust of 127.0.0.1, then parse XFF gated by saturn's own trusted_proxies.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_trusted_proxies.py --timeout=60 -v 2>&1 | tail -20
```

```output
            _post(origin, "/api/usage/report", {"tokens_in": 1, "tokens_out": 1}, headers)
            before = _get_usage(origin, admin, "5.5.5.5")
>           assert before.get("tokens_in", 0) == 0
E           AssertionError: assert 1 == 0
E            +  where 1 = <built-in method get of dict object at 0x109177ec0>('tokens_in', 0)
E            +    where <built-in method get of dict object at 0x109177ec0> = {'period': '2026-05-04', 'requests': 1, 'tokens_in': 1, 'tokens_out': 1, ...}.get

saturn/tests/test_trusted_proxies.py:219: AssertionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_trusted_proxies.py::test_empty_trusted_proxies_ignores_xff
FAILED saturn/tests/test_trusted_proxies.py::test_untrusted_peer_ignores_xff
FAILED saturn/tests/test_trusted_proxies.py::test_trusted_proxies_takes_effect_live
=================== 3 failed, 2 passed, 1 warning in 24.68s ====================
```
