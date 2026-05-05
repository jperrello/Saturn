# qj5.14 boot validators + LLM-honoured proof — red phase

*2026-05-04T20:45:20Z by Showboat 0.6.1*
<!-- showboat-id: 5eff56b4-54d5-4ad4-9dbf-ad50a123a11d -->

Spec: PRE_SPECS_B3.md §17.B. Two halves. Security half: 8 boot validators C.1.1-C.1.8 (missing/bad refuses, good accepts) + 2 structural invariants. LLM-honoured half: 6 fields × 2 backends (Ollama + OpenRouter sub-key) × 2 creation paths (existing TOML + POST /api/services). No mocks. Real subprocess for boot, real Ollama for free bulk, real OpenRouter for one keyed end-to-end.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_boot_validators.py saturn/tests/test_config_honoured.py --timeout=90 2>&1 | tail -30
```

```output
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/http/client.py:614: IncompleteRead
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_boot_validators.py::test_C1_1_admin_password_unset_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_1_admin_password_default_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_1_admin_password_short_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_2_admin_token_unset_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_2_admin_token_short_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_3_runner_token_unset_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_3_runner_token_short_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_4_lan_exposure_without_tokens_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_4_loopback_without_tokens_still_refuses_token_unset
FAILED saturn/tests/test_boot_validators.py::test_C1_5_beacon_without_budget_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_6_tls_cert_without_key_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_6_tls_world_readable_refuses
FAILED saturn/tests/test_boot_validators.py::test_C1_7_bad_cidr_refuses - ass...
FAILED saturn/tests/test_boot_validators.py::test_C1_8_wildcard_cors_refuses
FAILED saturn/tests/test_boot_validators.py::test_validator_reports_all_errors_in_one_pass
FAILED saturn/tests/test_boot_validators.py::test_dev_mode_logs_but_does_not_exit
FAILED saturn/tests/test_config_honoured.py::test_max_tokens_50_honoured_by_ollama[existing_ollama_service]
FAILED saturn/tests/test_config_honoured.py::test_max_tokens_50_honoured_by_ollama[new_ollama_service]
FAILED saturn/tests/test_config_honoured.py::test_model_id_honoured_by_ollama[existing_ollama_service]
FAILED saturn/tests/test_config_honoured.py::test_model_id_honoured_by_ollama[new_ollama_service]
======== 20 failed, 11 passed, 1 skipped, 1 warning in 99.82s (0:01:39) ========
```
