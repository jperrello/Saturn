# qj5.2 Saturn SVG → labeled Settings button + popup — red phase

*2026-05-04T20:19:19Z by Showboat 0.6.1*
<!-- showboat-id: fc804a5e-fb89-47cc-8ee6-455ebf34427c -->

Spec: replace top-left Saturn-ring SVG (chat-settings-btn at index.html:268/297) with a clearly-labeled Settings button (visible 'Settings' text per Nielsen H6). Clicking opens a per-chat popup containing the four style options (relocated from qj5.1), per-chat model override, current Saturn service. Real Saturn web + headless Chromium. No mocks.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_chat_ux_qj5_2.py --timeout=60 -v 2>&1 | tail -25
```

```output
                cls: popup.className || null,
                text_len: txt.length,
                has_model: /model/.test(txt),
                has_service: /(service|saturn)/.test(txt),
            };
        }""")
>       assert container is not None, (
            "after Settings click, no visible container holds all 4 style options "
            "(Default / Concise / Detailed / Code). The popup is missing."
        )
E       AssertionError: after Settings click, no visible container holds all 4 style options (Default / Concise / Detailed / Code). The popup is missing.
E       assert None is not None

saturn/tests/test_chat_ux_qj5_2.py:117: AssertionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_chat_ux_qj5_2.py::test_chat_settings_button_has_visible_label_text
FAILED saturn/tests/test_chat_ux_qj5_2.py::test_settings_click_reveals_popup_with_required_contents
======================== 2 failed, 1 warning in 15.23s =========================
```
