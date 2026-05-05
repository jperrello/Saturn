"""Saturn-qj5.13.4 — drift guard: AdminConfig.model_fields ↔ AC_FIELDS parity.

If Pydantic gains a new field but Web-UI/app.js AC_FIELDS doesn't, the UI silently
drops it on save. This meta-test enforces symmetric-difference == empty.
"""

import re
from pathlib import Path

from saturn.web import AdminConfig


LEGACY = {"model_filter", "max_budget", "budget_duration"}


def _ac_fields() -> set:
    src = (Path(__file__).resolve().parent.parent.parent / "Web-UI" / "app.js").read_text()
    start = src.find("const AC_FIELDS")
    assert start >= 0, "const AC_FIELDS not found in Web-UI/app.js"
    end = src.find("\n]", start)
    assert end >= 0, "AC_FIELDS array close not found"
    block = src[start:end]
    return set(re.findall(r"\[\s*'([^']+)'\s*,", block))


def test_admin_config_fields_parity():
    pyd = set(AdminConfig.model_fields.keys())
    js = _ac_fields()
    in_pyd_only = (pyd - js) - LEGACY
    in_js_only = js - pyd
    assert not in_pyd_only, (
        f"AdminConfig has fields missing from Web-UI/app.js AC_FIELDS: {sorted(in_pyd_only)!r}. "
        f"Add a row to AC_FIELDS for each so the UI load/save covers them."
    )
    assert not in_js_only, (
        f"Web-UI/app.js AC_FIELDS has fields missing from AdminConfig: {sorted(in_js_only)!r}. "
        f"Either remove the JS row or add the field to AdminConfig."
    )
