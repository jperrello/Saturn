import json
import os
from pathlib import Path
from typing import List


def _admin_config_path() -> Path:
    explicit = os.environ.get("SATURN_ADMIN_CONFIG_PATH")
    if explicit:
        return Path(explicit)
    d = os.environ.get("SATURN_DATA_DIR")
    base = Path(d) if d else Path(__file__).parent.parent / "data"
    return base / "admin_config.json"


def _load_admin_config() -> dict:
    p = _admin_config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _check_admin_password_env() -> List[str]:
    pw = os.environ.get("SATURN_ADMIN_PASSWORD")
    if pw is None:
        return ["SATURN_ADMIN_PASSWORD unset"]
    if pw == "saturn":
        return ['SATURN_ADMIN_PASSWORD is the default "saturn" — change it']
    if len(pw) < 12:
        return ["SATURN_ADMIN_PASSWORD shorter than 12 chars (too short)"]
    return []


def _check_admin_token_env() -> List[str]:
    t = os.environ.get("SATURN_ADMIN_TOKEN")
    if t is None:
        return ["SATURN_ADMIN_TOKEN unset"]
    if len(t) < 32:
        return ["SATURN_ADMIN_TOKEN shorter than 32 chars (too short)"]
    return []


def _check_runner_token_env() -> List[str]:
    t = os.environ.get("SATURN_RUNNER_TOKEN")
    if t is None:
        return ["SATURN_RUNNER_TOKEN unset"]
    if len(t) < 32:
        return ["SATURN_RUNNER_TOKEN shorter than 32 chars (too short)"]
    return []


def _check_lan_exposure_requires_auth() -> List[str]:
    bind = os.environ.get("SATURN_BIND_HOST", "127.0.0.1")
    if bind == "0.0.0.0":
        if not os.environ.get("SATURN_ADMIN_TOKEN") or not os.environ.get("SATURN_RUNNER_TOKEN"):
            return ["LAN exposure (bind=0.0.0.0) without admin or runner token"]
    return []


def _check_beacon_budgets() -> List[str]:
    errs: List[str] = []
    sd = os.environ.get("SATURN_SERVICES_DIR")
    if not sd:
        return errs
    p = Path(sd)
    if not p.exists():
        return errs
    for toml_file in p.glob("*.toml"):
        try:
            txt = toml_file.read_text()
        except Exception:
            continue
        if "[beacon]" in txt and "enabled = true" in txt:
            if "max_budget_usd" not in txt:
                errs.append(f"beacon service {toml_file.stem}: max_budget_usd missing")
    return errs


def _check_tls_pair() -> List[str]:
    cert = os.environ.get("SATURN_TLS_CERT")
    key = os.environ.get("SATURN_TLS_KEY")
    errs: List[str] = []
    if cert and not key:
        errs.append("tls_cert_path set but tls_key_path missing")
    if key and not cert:
        errs.append("tls_key_path set but tls_cert_path missing")
    for path, label in [(cert, "tls_cert_path"), (key, "tls_key_path")]:
        if path and Path(path).exists():
            mode = Path(path).stat().st_mode & 0o777
            if mode & 0o077:
                errs.append(f"{label} {path} mode 0{oct(mode)[2:]} too wide (permissions must be 0600)")
    return errs


def _check_trusted_proxies_cidrs(cfg: dict) -> List[str]:
    import ipaddress
    errs: List[str] = []
    for p in cfg.get("trusted_proxies") or []:
        try:
            ipaddress.ip_network(p, strict=False)
        except Exception:
            errs.append(f"trusted_proxies entry invalid CIDR: {p!r}")
    return errs


def _check_cors_no_wildcard(cfg: dict) -> List[str]:
    if os.environ.get("SATURN_DEV_MODE") == "1":
        return []
    errs: List[str] = []
    for o in cfg.get("cors_origins") or []:
        if "*" in str(o):
            errs.append('cors_origins wildcard "*" forbidden; set SATURN_DEV_MODE=1 to allow')
    return errs


def run_validators() -> List[str]:
    errs: List[str] = []
    errs += _check_admin_password_env()
    errs += _check_admin_token_env()
    errs += _check_runner_token_env()
    errs += _check_lan_exposure_requires_auth()
    errs += _check_beacon_budgets()
    errs += _check_tls_pair()
    cfg = _load_admin_config()
    errs += _check_trusted_proxies_cidrs(cfg)
    errs += _check_cors_no_wildcard(cfg)
    return errs
