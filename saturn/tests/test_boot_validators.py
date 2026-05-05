"""Saturn-qj5.14 — boot validators (the security half).

Per PRE_SPECS_B3.md §17.B.1-3. Eight checks (C.1.1-C.1.8); each gets a
missing/bad/good triple. Plus two structural invariants: multi-error
report + dev-mode short-circuit-but-still-log.

`saturn web` boot must:
  - run AdminConfig.validate(cfg)
  - aggregate errors[] from _check_admin_password_env, _check_admin_token_env,
    _check_runner_token_env, _check_lan_exposure_requires_auth,
    _check_beacon_budgets, _check_tls_pair, _check_trusted_proxies_cidrs,
    _check_cors_no_wildcard
  - if errors and not _dev_mode(): logger.error(...); sys.exit(1)

No mocks. Real subprocess.
"""

from .conftest_b3 import _boot, MIN_ADMIN_TOKEN, MIN_RUNNER_TOKEN, MIN_PASSWORD


_GOOD = {
    "SATURN_ADMIN_TOKEN":    MIN_ADMIN_TOKEN,
    "SATURN_RUNNER_TOKEN":   MIN_RUNNER_TOKEN,
    "SATURN_ADMIN_PASSWORD": MIN_PASSWORD,
    "SATURN_BIND_HOST":      "127.0.0.1",
}


# --- C.1.1 admin_password_env ---

def test_C1_1_admin_password_unset_refuses():
    code, err = _boot(env={"SATURN_ADMIN_TOKEN": MIN_ADMIN_TOKEN,
                           "SATURN_RUNNER_TOKEN": MIN_RUNNER_TOKEN})
    assert code == 1
    assert "SATURN_ADMIN_PASSWORD" in err and "unset" in err.lower()


def test_C1_1_admin_password_default_refuses():
    code, err = _boot(env={**_GOOD, "SATURN_ADMIN_PASSWORD": "saturn"})
    assert code == 1
    assert "default" in err.lower() and "saturn" in err.lower()


def test_C1_1_admin_password_short_refuses():
    code, err = _boot(env={**_GOOD, "SATURN_ADMIN_PASSWORD": "short"})
    assert code == 1
    assert "shorter than 12" in err.lower() or "12 chars" in err.lower() or "too short" in err.lower()


def test_C1_1_admin_password_good_accepts():
    code, _ = _boot(env=_GOOD)
    assert code == 0


# --- C.1.2 admin_token_env ---

def test_C1_2_admin_token_unset_refuses():
    code, err = _boot(env={"SATURN_RUNNER_TOKEN": MIN_RUNNER_TOKEN,
                           "SATURN_ADMIN_PASSWORD": MIN_PASSWORD})
    assert code == 1
    assert "SATURN_ADMIN_TOKEN" in err and "unset" in err.lower()


def test_C1_2_admin_token_short_refuses():
    code, err = _boot(env={**_GOOD, "SATURN_ADMIN_TOKEN": "x" * 16})
    assert code == 1
    assert "32" in err or "short" in err.lower()


def test_C1_2_admin_token_good_accepts():
    code, _ = _boot(env=_GOOD)
    assert code == 0


# --- C.1.3 runner_token_env ---

def test_C1_3_runner_token_unset_refuses():
    code, err = _boot(env={"SATURN_ADMIN_TOKEN": MIN_ADMIN_TOKEN,
                           "SATURN_ADMIN_PASSWORD": MIN_PASSWORD})
    assert code == 1
    assert "SATURN_RUNNER_TOKEN" in err and "unset" in err.lower()


def test_C1_3_runner_token_short_refuses():
    code, err = _boot(env={**_GOOD, "SATURN_RUNNER_TOKEN": "y" * 16})
    assert code == 1
    assert "32" in err or "short" in err.lower()


def test_C1_3_runner_token_good_accepts():
    code, _ = _boot(env=_GOOD)
    assert code == 0


# --- C.1.4 LAN exposure requires auth ---

def test_C1_4_lan_exposure_without_tokens_refuses():
    code, err = _boot(env={"SATURN_BIND_HOST": "0.0.0.0",
                           "SATURN_ADMIN_PASSWORD": MIN_PASSWORD})
    assert code == 1
    assert "LAN exposure" in err or ("0.0.0.0" in err and "token" in err.lower())


def test_C1_4_lan_exposure_with_tokens_accepts():
    code, _ = _boot(env={**_GOOD, "SATURN_BIND_HOST": "0.0.0.0"})
    assert code == 0


def test_C1_4_loopback_without_tokens_still_refuses_token_unset():
    # 127.0.0.1 still requires admin/runner tokens per C.1.2/C.1.3 (both must resolve).
    code, err = _boot(env={"SATURN_BIND_HOST": "127.0.0.1",
                           "SATURN_ADMIN_PASSWORD": MIN_PASSWORD})
    assert code == 1


# --- C.1.5 beacon services need max_budget_usd ---

def test_C1_5_beacon_without_budget_refuses(tmp_path, monkeypatch):
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "beacon-no-budget.toml").write_text(
        'name = "beacon-no-budget"\n'
        'deployment = "cloud"\n'
        'api_type = "openrouter"\n'
        'priority = 30\n'
        '[upstream]\n'
        'base_url = "https://openrouter.ai/api/v1"\n'
        '[server]\n'
        'port = 0\n'
        '[beacon]\n'
        'enabled = true\n'
        'provider = "openrouter"\n'
    )
    monkeypatch.setenv("SATURN_SERVICES_DIR", str(services_dir))
    code, err = _boot(env={**_GOOD, "SATURN_SERVICES_DIR": str(services_dir)})
    assert code == 1
    assert "max_budget_usd" in err and "beacon" in err.lower()


def test_C1_5_beacon_with_budget_accepts(tmp_path):
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "beacon-budgeted.toml").write_text(
        'name = "beacon-budgeted"\n'
        'deployment = "cloud"\n'
        'api_type = "openrouter"\n'
        'priority = 30\n'
        '[upstream]\n'
        'base_url = "https://openrouter.ai/api/v1"\n'
        'max_budget_usd = 1.00\n'
        '[server]\n'
        'port = 0\n'
        '[beacon]\n'
        'enabled = true\n'
        'provider = "openrouter"\n'
    )
    code, _ = _boot(env={**_GOOD, "SATURN_SERVICES_DIR": str(services_dir)})
    assert code == 0


def test_C1_5_no_beacon_no_budget_required(tmp_path):
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "plain.toml").write_text(
        'name = "plain"\n'
        'deployment = "local"\n'
        'api_type = "ollama"\n'
        'priority = 50\n'
        '[upstream]\n'
        'base_url = "http://localhost:11434/v1"\n'
        '[server]\n'
        'port = 0\n'
        '[beacon]\n'
        'enabled = false\n'
    )
    code, _ = _boot(env={**_GOOD, "SATURN_SERVICES_DIR": str(services_dir)})
    assert code == 0


# --- C.1.6 TLS pair ---

def test_C1_6_tls_cert_without_key_refuses(tmp_path):
    cert = tmp_path / "cert.pem"
    cert.write_text("dummy")
    cert.chmod(0o600)
    code, err = _boot(env={**_GOOD, "SATURN_TLS_CERT": str(cert)})
    assert code == 1
    assert "tls_key_path" in err.lower() or "tls_cert_path set but" in err.lower()


def test_C1_6_tls_world_readable_refuses(tmp_path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("dummy"); key.write_text("dummy")
    cert.chmod(0o644)
    key.chmod(0o644)
    code, err = _boot(env={**_GOOD, "SATURN_TLS_CERT": str(cert), "SATURN_TLS_KEY": str(key)})
    assert code == 1
    assert "0644" in err or "permissions" in err.lower() or "too wide" in err.lower()


def test_C1_6_tls_unset_accepts():
    code, _ = _boot(env=_GOOD)
    assert code == 0


# --- C.1.7 trusted_proxies CIDRs ---

def test_C1_7_bad_cidr_refuses(tmp_path):
    admin_cfg = tmp_path / "admin_config.json"
    admin_cfg.write_text('{"trusted_proxies": ["10.0.0.999"]}')
    code, err = _boot(env={**_GOOD, "SATURN_ADMIN_CONFIG_PATH": str(admin_cfg)})
    assert code == 1
    assert "trusted_proxies" in err and ("CIDR" in err or "cidr" in err.lower() or "10.0.0.999" in err)


def test_C1_7_good_cidrs_accepts(tmp_path):
    admin_cfg = tmp_path / "admin_config.json"
    admin_cfg.write_text('{"trusted_proxies": ["10.0.0.0/8", "192.168.1.0/24"]}')
    code, _ = _boot(env={**_GOOD, "SATURN_ADMIN_CONFIG_PATH": str(admin_cfg)})
    assert code == 0


def test_C1_7_empty_list_accepts(tmp_path):
    admin_cfg = tmp_path / "admin_config.json"
    admin_cfg.write_text('{"trusted_proxies": []}')
    code, _ = _boot(env={**_GOOD, "SATURN_ADMIN_CONFIG_PATH": str(admin_cfg)})
    assert code == 0


# --- C.1.8 cors_origins no wildcard ---

def test_C1_8_wildcard_cors_refuses(tmp_path):
    admin_cfg = tmp_path / "admin_config.json"
    admin_cfg.write_text('{"cors_origins": ["*"]}')
    code, err = _boot(env={**_GOOD, "SATURN_ADMIN_CONFIG_PATH": str(admin_cfg)})
    assert code == 1
    assert "cors_origins" in err and "*" in err and "SATURN_DEV_MODE" in err


def test_C1_8_wildcard_cors_dev_mode_accepts(tmp_path):
    admin_cfg = tmp_path / "admin_config.json"
    admin_cfg.write_text('{"cors_origins": ["*"]}')
    code, err = _boot(env={**_GOOD, "SATURN_ADMIN_CONFIG_PATH": str(admin_cfg), "SATURN_DEV_MODE": "1"})
    assert code == 0


def test_C1_8_specific_origins_accepts(tmp_path):
    admin_cfg = tmp_path / "admin_config.json"
    admin_cfg.write_text('{"cors_origins": ["http://localhost:3000", "https://example.com"]}')
    code, _ = _boot(env={**_GOOD, "SATURN_ADMIN_CONFIG_PATH": str(admin_cfg)})
    assert code == 0


# --- Structural invariants ---

def test_validator_reports_all_errors_in_one_pass(tmp_path):
    admin_cfg = tmp_path / "admin_config.json"
    admin_cfg.write_text('{"trusted_proxies": ["bad-cidr"], "cors_origins": ["*"]}')
    code, err = _boot(env={"SATURN_ADMIN_PASSWORD": "saturn",
                           "SATURN_ADMIN_CONFIG_PATH": str(admin_cfg)})
    assert code == 1
    error_lines = [l for l in err.splitlines() if l.strip()]
    assert len(error_lines) >= 3, (
        f"expected ≥3 error lines (admin password + CIDR + CORS at minimum); got {len(error_lines)}: {error_lines!r}"
    )


def test_dev_mode_logs_but_does_not_exit():
    code, err = _boot(env={"SATURN_DEV_MODE": "1",
                           "SATURN_ADMIN_PASSWORD": "saturn",
                           "SATURN_ADMIN_TOKEN": MIN_ADMIN_TOKEN,
                           "SATURN_RUNNER_TOKEN": MIN_RUNNER_TOKEN})
    assert code == 0
    assert "default" in err.lower() and "saturn" in err.lower(), (
        "dev mode must still surface the validation error in stderr (logged, not fatal)"
    )
