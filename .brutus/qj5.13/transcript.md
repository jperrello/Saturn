# qj5.13 Configure page schema lift — red phase

*2026-05-04T20:55:06Z by Showboat 0.6.1*
<!-- showboat-id: 26e20450-d8ef-49f8-931e-110c29dd1cb9 -->

Spec: PRE_SPECS_B3.md §17.A. Lift admin_config.json from 3 fields (model_filter, max_budget, budget_duration) to ~22 fields across CONFIG_FIELDS A.2-A.8. Test layers: round-trip (every field POST→GET losslessly), restart preservation, live propagation (rate_rpm hits 429 without restart), refuse-on-invalid (every C.x violation → 422). Plus meta-test: every new AdminConfig field has a round-trip row.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_admin_config_qj5_13.py --timeout=60 2>&1 | tail -10
```

```output
FAILED saturn/tests/test_admin_config_qj5_13.py::test_config_survives_restart
FAILED saturn/tests/test_admin_config_qj5_13.py::test_rate_rpm_takes_effect_live
FAILED saturn/tests/test_admin_config_qj5_13.py::test_invalid_value_refused[trusted_proxies-value0]
FAILED saturn/tests/test_admin_config_qj5_13.py::test_invalid_value_refused[bind_host-999.999.999.999]
FAILED saturn/tests/test_admin_config_qj5_13.py::test_invalid_value_refused[admin_session_ttl_s-30]
FAILED saturn/tests/test_admin_config_qj5_13.py::test_invalid_value_refused[rate_rpm-0]
FAILED saturn/tests/test_admin_config_qj5_13.py::test_invalid_value_refused[trust_mode-open]
FAILED saturn/tests/test_admin_config_qj5_13.py::test_invalid_value_refused[cors_origins-value6]
FAILED saturn/tests/test_admin_config_qj5_13.py::test_invalid_value_refused[proxy_models_method-DELETE]
============= 29 failed, 4 passed, 1 warning in 149.98s (0:02:29) ==============
```
