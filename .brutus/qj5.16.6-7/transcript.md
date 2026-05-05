# qj5.16.6+.7 proxy body/query key removal — red phase

*2026-05-04T19:45:23Z by Showboat 0.6.1*
<!-- showboat-id: 3d43f2d1-196c-4d36-8040-cc3250c672a5 -->

Combined contract per SECURITY_AUDIT §11+§12 (geoff). F-5: delete api_key from ManualChatRequest (extra='forbid'); read inbound Authorization header verbatim; sanitise upstream error echo at saturn/web.py:794-796. F-6: drop api_key Query() from /api/proxy/models; read inbound Authorization; sanitise 502 message (no upstream URL/exception leak). Real local http server upstream — no mocks.

```bash
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_proxy_no_body_keys.py -v 2>&1 | tail -25
```

```output
E           {"detail":"Failed to fetch models: Client error '401 Unauthorized' for url 'http://127.0.0.1:55311/models'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401"}
E         ?                                                                             ++++++++++++++++++++++

saturn/tests/test_proxy_no_body_keys.py:163: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-05-04 12:45:27,298 - INFO - HTTP Request: GET http://127.0.0.1:55311/models "HTTP/1.0 401 Unauthorized"
2026-05-04 12:45:27,299 - INFO - HTTP Request: GET http://testserver/api/proxy/models?base_url=http://127.0.0.1:55311 "HTTP/1.1 502 Bad Gateway"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: GET http://127.0.0.1:55311/models "HTTP/1.0 401 Unauthorized"
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/api/proxy/models?base_url=http://127.0.0.1:55311 "HTTP/1.1 502 Bad Gateway"
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_proxy_no_body_keys.py::test_proxy_chat_rejects_body_api_key
FAILED saturn/tests/test_proxy_no_body_keys.py::test_proxy_chat_passthrough_authorization_header
FAILED saturn/tests/test_proxy_no_body_keys.py::test_proxy_chat_does_not_echo_upstream_error_body
FAILED saturn/tests/test_proxy_no_body_keys.py::test_proxy_models_rejects_query_api_key
FAILED saturn/tests/test_proxy_no_body_keys.py::test_proxy_models_passthrough_authorization_header
FAILED saturn/tests/test_proxy_no_body_keys.py::test_proxy_models_502_does_not_leak_upstream_details
========================= 6 failed, 1 warning in 4.09s =========================
```
