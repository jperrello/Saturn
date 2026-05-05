# qj5.1 remove top-right style pill — red phase

*2026-05-04T19:54:15Z by Showboat 0.6.1*
<!-- showboat-id: dc055c94-0e3a-4d74-99ff-18f77e7a3442 -->

Spec: the four-option pill (Default/Concise/Detailed/Code) at index.html:299-304 inside .strip-right must be removed from the Chat tab. Style selection relocates to the per-chat Settings popup (qj5.2 — separate bead). Real Saturn web + headless Chromium via tests.harness.web.serve() + playwright. No mocks.

```bash
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_chat_ux_qj5_1.py -v 2>&1 | tail -20
```

```output
                ready = True
                break
            except (urllib.error.URLError, ConnectionResetError, OSError):
                time.sleep(0.3)
        if not ready:
>           os.killpg(proc.pid, signal.SIGTERM)
E           PermissionError: [Errno 1] Operation not permitted

tests/harness/web.py:41: PermissionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR saturn/tests/test_chat_ux_qj5_1.py::test_style_pill_removed_by_id - Per...
ERROR saturn/tests/test_chat_ux_qj5_1.py::test_no_style_select_in_top_strip
======================== 1 warning, 2 errors in 20.42s =========================
```

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_chat_ux_qj5_1.py -v 2>&1 | tail -20
```

```output
            if {"default", "concise", "detailed", "code"} <= opt_set:
                offending.append(opts)
>       assert not offending, (
            f"top-strip <select> still exposes the response-style pill options: {offending}"
        )
E       AssertionError: top-strip <select> still exposes the response-style pill options: [['default', 'concise', 'detailed', 'code']]
E       assert not [['default', 'concise', 'detailed', 'code']]

saturn/tests/test_chat_ux_qj5_1.py:52: AssertionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_chat_ux_qj5_1.py::test_style_pill_removed_by_id - As...
FAILED saturn/tests/test_chat_ux_qj5_1.py::test_no_style_select_in_top_strip
========================= 2 failed, 1 warning in 8.23s =========================
```
