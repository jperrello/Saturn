import os
import sys
import re
import subprocess
import signal
import time
import asyncio
import logging
import socket
import sqlite3
import json
from collections import deque, OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List
from dataclasses import asdict

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import (
    list_service_configs,
    load_service_config,
    ensure_services_dir,
    get_config_path,
    ServiceConfig,
    BUILTIN_SERVICES_DIR,
)
from .runner import (
    read_service_info,
    remove_service_info,
    _pid_alive,
    RUN_DIR,
)
from .discovery import discover, asdict as dc_asdict
from .mcp_client import manager as mcp_manager

logger = logging.getLogger("saturn.web")

def _webdir():
    try:
        from . import webui
        return Path(webui.__file__).parent
    except ImportError:
        return Path(__file__).parent.parent / "Web-UI"


WEB_DIR = _webdir()


@asynccontextmanager
async def lifespan(app):
    try:
        apply_admin_config(_load_admin_config())
    except Exception:
        pass
    yield
    # kill child services started by this server instance
    for pid in list(_started_pids):
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    # give children a moment to exit, then force-kill stragglers
    time.sleep(1)
    for pid in list(_started_pids):
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    _started_pids.clear()
    # kill tunnel if running
    if _tunnel_proc and _tunnel_proc.returncode is None:
        _tunnel_proc.terminate()


app = FastAPI(title="Saturn Web UI", lifespan=lifespan)


# --- Web UI session gate (Saturn-828) ---

import hashlib as _hashlib
import secrets as _secrets

DEFAULT_GATE_PASSWORD = "Saturn"
SESSION_COOKIE = "saturn_session"
SESSION_TTL_S = 60 * 60 * 12

_sessions: dict[str, float] = {}

GATE_OPEN_PATHS = {
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/status",
    "/api/auth/password",
    "/login",
    "/login.html",
    "/v1/health",
    "/favicon.ico",
}


def _gate_state() -> dict:
    cfg = _load_admin_config()
    return cfg.get("gate") or {}


def _gate_save(state: dict):
    cfg = _load_admin_config()
    cfg["gate"] = state
    _save_admin_config(cfg)


def _hash_pw(pw: str, salt: str) -> str:
    return _hashlib.scrypt(pw.encode(), salt=salt.encode(), n=2**14, r=8, p=1, dklen=32).hex()


def _ensure_gate() -> dict:
    state = _gate_state()
    if state.get("hash") and state.get("salt"):
        return state
    salt = _secrets.token_hex(16)
    state = {
        "salt": salt,
        "hash": _hash_pw(DEFAULT_GATE_PASSWORD, salt),
        "must_change": True,
    }
    _gate_save(state)
    return state


def _verify_pw(pw: str) -> bool:
    import hmac
    state = _ensure_gate()
    candidate = _hash_pw(pw or "", state["salt"])
    return hmac.compare_digest(candidate, state["hash"])


def _new_session() -> str:
    token = _secrets.token_urlsafe(32)
    _sessions[token] = time.time() + SESSION_TTL_S
    if len(_sessions) > 1000:
        for k in [k for k, exp in _sessions.items() if exp < time.time()]:
            _sessions.pop(k, None)
    return token


def _session_valid(token: Optional[str]) -> bool:
    if not token:
        return False
    exp = _sessions.get(token)
    if not exp:
        return False
    if exp < time.time():
        _sessions.pop(token, None)
        return False
    return True


def _has_session(request: Request) -> bool:
    return _session_valid(request.cookies.get(SESSION_COOKIE))


def _has_bearer(request: Request) -> bool:
    import hmac
    expected = os.environ.get(ADMIN_TOKEN_ENV, "")
    if not expected:
        return False
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return False
    return hmac.compare_digest(auth.split(" ", 1)[1].strip(), expected)


@app.middleware("http")
async def gate_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/v1/"):
        return await call_next(request)
    if path in GATE_OPEN_PATHS:
        return await call_next(request)
    if _has_session(request) or _has_bearer(request):
        return await call_next(request)
    if path.startswith("/admin/") or path == "/configure":
        return JSONResponse({"error": "auth_required"}, status_code=401)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login", status_code=303)


class _LoginBody(BaseModel):
    password: str


class _ChangePwBody(BaseModel):
    old: str
    new: str


@app.get("/api/auth/status")
async def auth_status(request: Request):
    state = _ensure_gate()
    return {
        "authenticated": _has_session(request),
        "must_change": bool(state.get("must_change")),
    }


@app.post("/api/auth/login")
async def auth_login(body: _LoginBody):
    if not _verify_pw(body.password):
        raise HTTPException(401, "Invalid password")
    token = _new_session()
    state = _ensure_gate()
    resp = JSONResponse({"ok": True, "must_change": bool(state.get("must_change"))})
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL_S, httponly=True, samesite="lax", path="/")
    return resp


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    tok = request.cookies.get(SESSION_COOKIE)
    if tok:
        _sessions.pop(tok, None)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@app.post("/api/auth/password")
async def auth_password(body: _ChangePwBody, request: Request):
    state = _ensure_gate()
    if not _has_session(request) and not state.get("must_change"):
        raise HTTPException(401, "auth_required")
    if not _verify_pw(body.old):
        raise HTTPException(401, "Invalid current password")
    if len(body.new) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    salt = _secrets.token_hex(16)
    _gate_save({"salt": salt, "hash": _hash_pw(body.new, salt), "must_change": False})
    _sessions.clear()
    token = _new_session()
    resp = JSONResponse({"ok": True})
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL_S, httponly=True, samesite="lax", path="/")
    return resp


@app.get("/login")
async def login_page():
    page = WEB_DIR / "login.html"
    if page.is_file():
        return FileResponse(page)
    raise HTTPException(404, "login.html missing")


# --- API Models ---

class _UpstreamCreate(BaseModel):
    base_url: str = ""
    api_key_env: Optional[str] = None


class ServiceCreate(BaseModel):
    name: str
    deployment: str = "cloud"
    api_type: str = "openai"
    priority: int = 50
    base_url: str = ""
    api_key_env: Optional[str] = None
    upstream: Optional[_UpstreamCreate] = None
    port: int = 0
    beacon_enabled: bool = False
    beacon_provider: Optional[str] = None
    rotation_interval: int = 300
    expiration_interval: int = 600
    max_budget: Optional[float] = None
    max_budget_unit: Optional[str] = None


class ServiceStart(BaseModel):
    host: str = "0.0.0.0"
    port: Optional[int] = None


# --- Helpers ---

def _status(name: str) -> dict:
    info = read_service_info(name)
    if not info:
        return {"running": False}
    pid = info.get("pid")
    if pid and _pid_alive(pid):
        return {"running": True, "pid": pid, "port": info.get("port"), "mdns_name": info.get("mdns_name")}
    remove_service_info(name)
    return {"running": False}


def _config_to_dict(name: str, config: ServiceConfig, builtin: bool) -> dict:
    status = _status(name)
    return {
        "name": name,
        "deployment": config.deployment,
        "api_type": config.api_type,
        "priority": config.priority,
        "max_budget": config.max_budget,
        "max_budget_unit": config.max_budget_unit,
        "base_url": config.upstream.base_url,
        "api_key_env": config.upstream.api_key_env,
        "port": config.server.port,
        "module": config.server.module,
        "beacon_enabled": config.beacon.enabled,
        "beacon_provider": config.beacon.provider,
        "rotation_interval": config.beacon.rotation_interval,
        "expiration_interval": config.beacon.expiration_interval,
        "builtin": builtin,
        **status,
    }


# --- Brutus state ---

_breakers: dict[str, dict] = {}  # name -> {failures, opened_at, health_fails}
_failover_hysteresis: dict = {"name": None, "at": 0.0}  # last peer used when no convo_id
HYSTERESIS_S = 30.0
MAX_STICKY = 10000
MAX_STICKY_PER_IP = 100
STICKY_TTL_S = 3600.0


def _alias_peer(name: str) -> str:
    import hashlib
    return hashlib.sha256((name or "").encode("utf-8")).hexdigest()[:8]


class _StickyMap(OrderedDict):
    def __init__(self):
        super().__init__()
        self._by_ip: dict = {}

    def _ttl(self):
        return globals().get("STICKY_TTL_S", 3600.0)

    def _purge_expired(self):
        cutoff = time.time() - self._ttl()
        for k in list(OrderedDict.keys(self)):
            ts, _ = OrderedDict.__getitem__(self, k)
            if ts < cutoff:
                OrderedDict.__delitem__(self, k)
                self._drop_from_buckets(k)
            else:
                break

    def _drop_from_buckets(self, key):
        for ip, bucket in list(self._by_ip.items()):
            if key in bucket:
                bucket.remove(key)
                if not bucket:
                    self._by_ip.pop(ip, None)
                return

    def __setitem__(self, key, value):
        self._purge_expired()
        OrderedDict.__setitem__(self, key, (time.time(), value))
        OrderedDict.move_to_end(self, key)
        cap = globals().get("MAX_STICKY", 10000)
        while len(self) > cap:
            old, _ = OrderedDict.popitem(self, last=False)
            self._drop_from_buckets(old)

    def set_with_ip(self, key, value, ip):
        bucket = self._by_ip.setdefault(ip, [])
        per_ip_cap = globals().get("MAX_STICKY_PER_IP", 100)
        while len(bucket) >= per_ip_cap:
            old = bucket.pop(0)
            try:
                OrderedDict.__delitem__(self, old)
            except KeyError:
                pass
        if key in bucket:
            bucket.remove(key)
        self[key] = value
        bucket.append(key)

    def clear(self):
        super().clear()
        self._by_ip.clear()

    def __contains__(self, key):
        if not OrderedDict.__contains__(self, key):
            return False
        ts, _ = OrderedDict.__getitem__(self, key)
        return time.time() - ts <= self._ttl()

    def get(self, key, default=None):
        if not OrderedDict.__contains__(self, key):
            return default
        ts, value = OrderedDict.__getitem__(self, key)
        if time.time() - ts > self._ttl():
            return default
        return value

    def __getitem__(self, key):
        if not OrderedDict.__contains__(self, key):
            raise KeyError(key)
        ts, value = OrderedDict.__getitem__(self, key)
        if time.time() - ts > self._ttl():
            raise KeyError(key)
        return value


_failover_state = _StickyMap()  # conversation_id -> peer_name (sticky), bounded


def _set_sticky(convo_id: str, peer: str, ip: str) -> None:
    _failover_state.set_with_ip(convo_id, peer, ip)
_health: dict[str, bool] = {}
_tunnel_proc: Optional[asyncio.subprocess.Process] = None
_tunnel_url: Optional[str] = None
_routing_log: deque = deque(maxlen=50)
_started_pids: set[int] = set()  # PIDs of services started by this server instance

BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN = 30


def _breaker(name: str) -> dict:
    if name not in _breakers:
        _breakers[name] = {"failures": 0, "opened_at": 0}
    return _breakers[name]


def _breaker_open(b: dict) -> bool:
    if b["failures"] < BREAKER_THRESHOLD:
        return False
    if time.time() - b["opened_at"] > BREAKER_COOLDOWN:
        b["failures"] = 0
        return False
    return True


def _record_failure(name: str):
    b = _breaker(name)
    b["failures"] += 1
    if b["failures"] >= BREAKER_THRESHOLD:
        b["opened_at"] = time.time()


def _record_success(name: str):
    _breaker(name)["failures"] = 0


def _lan_ip() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


# --- Rate Limiting (SAT-2n8.1) ---

class Bucket:
    def __init__(self, capacity, rate):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.rate = rate  # tokens per second
        self.last = time.monotonic()

    def consume(self, n=1):
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False

    def remaining(self):
        now = time.monotonic()
        return min(self.capacity, self.tokens + (now - self.last) * self.rate)

    def retry_after(self, n=1):
        deficit = n - self.remaining()
        if deficit <= 0:
            return 0
        return deficit / self.rate


RATE_RPM = int(os.environ.get("SATURN_RATE_RPM", "30"))
RATE_TPM = int(os.environ.get("SATURN_RATE_TPM", "100000"))
RATE_CONCURRENT_PER_IP = int(os.environ.get("SATURN_RATE_CONCURRENT", "3"))
RATE_CONCURRENT_GLOBAL = int(os.environ.get("SATURN_RATE_GLOBAL_CONCURRENT", "10"))

_rpm_buckets: dict[str, Bucket] = {}
_tpm_buckets: dict[str, Bucket] = {}
_ip_semaphores: dict[str, asyncio.Semaphore] = {}
_global_semaphore = asyncio.Semaphore(RATE_CONCURRENT_GLOBAL)
_ip_active: dict[str, int] = {}  # track active requests per IP


def _rpm_bucket(ip: str) -> Bucket:
    if ip not in _rpm_buckets:
        _rpm_buckets[ip] = Bucket(RATE_RPM, RATE_RPM / 60.0)
    return _rpm_buckets[ip]


def _tpm_bucket(ip: str) -> Bucket:
    if ip not in _tpm_buckets:
        _tpm_buckets[ip] = Bucket(RATE_TPM, RATE_TPM / 60.0)
    return _tpm_buckets[ip]


def _ip_sem(ip: str) -> asyncio.Semaphore:
    if ip not in _ip_semaphores:
        _ip_semaphores[ip] = asyncio.Semaphore(RATE_CONCURRENT_PER_IP)
    return _ip_semaphores[ip]


_trusted_nets: list = []


def _set_trusted_proxies(cidrs):
    import ipaddress
    global _trusted_nets
    nets = []
    for c in cidrs or []:
        try:
            nets.append(ipaddress.ip_network(c, strict=False))
        except Exception:
            logger.warning(f"trusted_proxies: skipping invalid CIDR {c!r}")
    _trusted_nets = nets


def _client_ip(request: Request) -> str:
    import ipaddress
    peer = request.client.host if request.client else "unknown"
    if not _trusted_nets:
        return peer
    try:
        peer_ip = ipaddress.ip_address(peer)
    except Exception:
        return peer
    if not any(peer_ip in n for n in _trusted_nets):
        return peer
    xff = request.headers.get("x-forwarded-for")
    if not xff:
        return peer
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    if not parts:
        return peer
    return parts[-1]


def _check_rate(ip: str) -> Optional[JSONResponse]:
    rpm = _rpm_bucket(ip)
    if not rpm.consume():
        retry = max(1, int(rpm.retry_after()))
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "retry_after": retry},
            headers={
                "Retry-After": str(retry),
                "X-Saturn-Tokens-Remaining": str(int(rpm.remaining())),
            },
        )
    return None


def _check_tpm(ip: str, tokens: int) -> Optional[JSONResponse]:
    tpm = _tpm_bucket(ip)
    if not tpm.consume(tokens):
        retry = max(1, int(tpm.retry_after(tokens)))
        return JSONResponse(
            status_code=429,
            content={"error": "Token rate limit exceeded", "retry_after": retry},
            headers={
                "Retry-After": str(retry),
                "X-Saturn-Tokens-Remaining": str(int(tpm.remaining())),
            },
        )
    return None


# --- Token Quotas & SQLite (SAT-2n8.2) ---

_data_dir_env = os.environ.get("SATURN_DATA_DIR")
DB_PATH = Path(_data_dir_env) / "saturn.db" if _data_dir_env else Path(__file__).parent.parent / "data" / "saturn.db"


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS usage (
        user_id TEXT,
        period TEXT,
        tokens_in INTEGER DEFAULT 0,
        tokens_out INTEGER DEFAULT 0,
        requests INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_user_period
        ON usage(user_id, period)""")
    conn.commit()
    return conn


def _record_usage(ip: str, tokens_in: int, tokens_out: int):
    period = time.strftime("%Y-%m-%d")
    conn = _db()
    conn.execute("""INSERT INTO usage (user_id, period, tokens_in, tokens_out, requests, updated_at)
        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, period) DO UPDATE SET
            tokens_in = tokens_in + excluded.tokens_in,
            tokens_out = tokens_out + excluded.tokens_out,
            requests = requests + 1,
            updated_at = CURRENT_TIMESTAMP""",
        (ip, period, tokens_in, tokens_out))
    conn.commit()
    conn.close()


# --- Model Allowlist/Blocklist (SAT-2n8.3) ---

MODEL_FILTER = os.environ.get("SATURN_MODEL_FILTER", "")


def _parse_filter(spec: str) -> tuple[set, set]:
    allow = set()
    block = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("+"):
            allow.add(part[1:].lower())
        elif part.startswith("-"):
            block.add(part[1:].lower())
    return allow, block


def _filter_models(models: list[dict], spec: str) -> list[dict]:
    if not spec:
        return models
    allow, block = _parse_filter(spec)
    if "all" in block:
        return [m for m in models if m.get("id", "").lower() in allow]
    if "all" in allow:
        return [m for m in models if m.get("id", "").lower() not in block]
    result = []
    for m in models:
        mid = m.get("id", "").lower()
        if mid in block:
            continue
        if allow and mid not in allow:
            continue
        result.append(m)
    return result


# --- Admin settings (server-side config) ---

_admin_config: dict = {}


def _admin_config_path() -> Path:
    explicit = os.environ.get("SATURN_ADMIN_CONFIG_PATH")
    if explicit:
        return Path(explicit)
    d = os.environ.get("SATURN_DATA_DIR")
    base = Path(d) if d else Path(__file__).parent.parent / "data"
    return base / "admin_config.json"


def _load_admin_config() -> dict:
    global _admin_config
    config_path = _admin_config_path()
    if config_path.exists():
        try:
            _admin_config = json.loads(config_path.read_text())
        except Exception:
            _admin_config = {}
    return _admin_config


def _save_admin_config(config: dict):
    global _admin_config
    _admin_config = config
    config_path = _admin_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))


def _model_filter() -> str:
    cfg = _load_admin_config()
    return cfg.get("model_filter", MODEL_FILTER)


ADMIN_PASSWORD = os.environ.get("SATURN_ADMIN_PASSWORD", "saturn")
ADMIN_TOKEN_ENV = os.environ.get("SATURN_ADMIN_TOKEN_ENV", "SATURN_ADMIN_TOKEN")


def require_admin(request: Request, authorization: Optional[str] = Header(default=None)):
    import hmac
    if _has_session(request):
        return True
    expected = os.environ.get(ADMIN_TOKEN_ENV, "")
    bad = HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})
    if not expected:
        raise bad
    if not authorization or not authorization.lower().startswith("bearer "):
        raise bad
    presented = authorization.split(" ", 1)[1].strip()
    if not hmac.compare_digest(presented, expected):
        raise bad
    return True


class AdminAuth(BaseModel):
    password: str


@app.post("/api/admin/auth")
async def admin_auth(body: AdminAuth):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Invalid password")
    token = os.environ.get(ADMIN_TOKEN_ENV, "")
    return {"ok": True, "token": token}


# --- API Routes ---

@app.get("/api/services")
async def services(_=Depends(require_admin)):
    configs = list_service_configs()
    return [_config_to_dict(name, cfg, builtin) for name, cfg, builtin in configs]


@app.post("/api/services")
async def create(body: ServiceCreate, _=Depends(require_admin)):
    if load_service_config(body.name):
        raise HTTPException(400, f"Service '{body.name}' already exists")
    if (BUILTIN_SERVICES_DIR / f"{body.name}.toml").exists():
        raise HTTPException(400, f"'{body.name}' is a built-in service name")

    base_url = body.upstream.base_url if body.upstream and body.upstream.base_url else body.base_url
    api_key_env = body.upstream.api_key_env if body.upstream and body.upstream.api_key_env else body.api_key_env

    ensure_services_dir()
    lines = [
        f'name = "{body.name}"',
        f'deployment = "{body.deployment}"',
        f'api_type = "{body.api_type}"',
        f'priority = {body.priority}',
    ]
    if body.max_budget is not None:
        lines.append(f"max_budget = {body.max_budget}")
        lines.append(f'max_budget_unit = "{body.max_budget_unit or "usd"}"')
    lines += [
        "",
        "[upstream]",
        f'base_url = "{base_url}"',
    ]
    if api_key_env:
        lines.append(f'api_key_env = "{api_key_env}"')
    lines += ["", "[server]", f"port = {body.port}", "", "[beacon]", f"enabled = {'true' if body.beacon_enabled else 'false'}"]
    if body.beacon_enabled and body.beacon_provider:
        lines.append(f'provider = "{body.beacon_provider}"')
        lines.append(f"rotation_interval = {body.rotation_interval}")
        lines.append(f"expiration_interval = {body.expiration_interval}")

    get_config_path(body.name).write_text("\n".join(lines) + "\n")
    config = load_service_config(body.name)
    return _config_to_dict(body.name, config, False)


@app.post("/api/services/{name}/start")
async def start(name: str, body: ServiceStart = None, _=Depends(require_admin)):
    if body is None:
        body = ServiceStart()
    config = load_service_config(name)
    if not config:
        raise HTTPException(404, f"Service '{name}' not found")

    status = _status(name)
    if status["running"]:
        raise HTTPException(409, f"Service '{name}' is already running")

    cmd = [sys.executable, "-m", "saturn", "run", name]
    if body.port:
        cmd += ["--port", str(body.port)]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    _started_pids.add(proc.pid)

    # wait briefly for service info file to appear
    for _ in range(20):
        time.sleep(0.25)
        info = read_service_info(name)
        if info and _pid_alive(info.get("pid", 0)):
            _started_pids.discard(proc.pid)
            _started_pids.add(info["pid"])
            return {"started": True, "pid": info["pid"], "port": info.get("port")}

    return {"started": True, "pid": proc.pid, "port": None}


@app.post("/api/services/{name}/stop")
async def stop(name: str, _=Depends(require_admin)):
    info = read_service_info(name)
    if not info or "pid" not in info:
        raise HTTPException(404, f"Service '{name}' is not running")

    pid = info["pid"]
    if not _pid_alive(pid):
        remove_service_info(name)
        raise HTTPException(404, f"Service '{name}' is not running (stale)")

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        raise HTTPException(500, f"Failed to stop: {e}")

    for _ in range(30):
        time.sleep(0.1)
        if not _pid_alive(pid):
            break

    remove_service_info(name)
    _started_pids.discard(pid)
    return {"stopped": True, "name": name}


@app.put("/api/services/{name}")
async def update_service(name: str, body: ServiceCreate, _=Depends(require_admin)):
    if not load_service_config(name):
        raise HTTPException(404, f"Service '{name}' not found")
    if (BUILTIN_SERVICES_DIR / f"{name}.toml").exists():
        raise HTTPException(400, f"'{name}' is a built-in service")
    base_url = body.upstream.base_url if body.upstream and body.upstream.base_url else body.base_url
    api_key_env = body.upstream.api_key_env if body.upstream and body.upstream.api_key_env else body.api_key_env
    ensure_services_dir()
    lines = [
        f'name = "{name}"',
        f'deployment = "{body.deployment}"',
        f'api_type = "{body.api_type}"',
        f'priority = {body.priority}',
    ]
    if body.max_budget is not None:
        lines.append(f"max_budget = {body.max_budget}")
        lines.append(f'max_budget_unit = "{body.max_budget_unit or "usd"}"')
    lines += [
        "",
        "[upstream]",
        f'base_url = "{base_url}"',
    ]
    if api_key_env:
        lines.append(f'api_key_env = "{api_key_env}"')
    lines += ["", "[server]", f"port = {body.port}", "", "[beacon]", f"enabled = {'true' if body.beacon_enabled else 'false'}"]
    get_config_path(name).write_text("\n".join(lines) + "\n")
    return {"ok": True, "name": name}


@app.delete("/api/services/{name}")
async def delete(name: str, _=Depends(require_admin)):
    config_path = get_config_path(name)
    builtin_path = BUILTIN_SERVICES_DIR / f"{name}.toml"

    if builtin_path.exists() and not config_path.exists():
        raise HTTPException(400, f"Cannot delete built-in service '{name}'")
    if not config_path.exists():
        raise HTTPException(404, f"Service '{name}' not found")

    status = _status(name)
    if status["running"]:
        raise HTTPException(409, "Stop the service before deleting")

    config_path.unlink()
    return {"deleted": True, "name": name}


@app.get("/api/discover")
async def api_discover(request: Request):
    ip = _client_ip(request)
    blocked = _check_rate(ip)
    if blocked:
        return blocked
    from saturn.mdns.isolation import probe as _isolation_probe
    from dataclasses import asdict as _asdict
    loop = asyncio.get_event_loop()
    found = await loop.run_in_executor(None, lambda: discover(timeout=5.0, settle_time=1.0))
    result = []
    for s in found:
        entry = {
            "name": s.name,
            "host": s.host,
            "port": s.port,
            "status": "online",
            "priority": s.priority,
            "deployment": s.deployment,
            "api_type": s.api_type,
            "models": s.models,
            "node_id": s.node_id,
        }
        result.append(entry)
        _discovered[s.name] = entry
    iso = await loop.run_in_executor(None, lambda: _isolation_probe(timeout=4.0))
    return {"services": result, "isolation": _asdict(iso)}


# --- Service resolution ---

_discovered: dict = {}


def _resolve(name: str) -> tuple[str, dict[str, str]]:
    # check discovered services first
    if name in _discovered:
        d = _discovered[name]
        return f"http://{d['host']}:{d['port']}/v1", {}

    # check running configured services
    info = read_service_info(name)
    if info and _pid_alive(info.get("pid", 0)):
        port = info.get("port")
        if port:
            return f"http://127.0.0.1:{port}/v1", {}

    # fall back to configured base_url (for cloud services like openrouter)
    config = load_service_config(name)
    if not config:
        rejected = _known_nodes.latest_rejection(name)
        if rejected:
            expected = rejected.get("expected_node_id") or ""
            seen = rejected.get("node_id") or ""
            raise HTTPException(
                403,
                detail={
                    "error": "trust_rebind_rejected",
                    "service": name,
                    "expected_prefix": expected[:8],
                    "seen_prefix": seen[:8],
                    "seen_host": rejected.get("host_seen", ""),
                    "remediation": "Verify with the Saturn admin, then accept via Configure → Service identity → Trust this node_id.",
                },
            )
        raise HTTPException(404, f"Service '{name}' not found")
    headers = {}
    if config.upstream.api_key_env:
        key = os.environ.get(config.upstream.api_key_env, "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
    return config.upstream.base_url, headers


OPENAI_PARAMS = {"temperature", "max_tokens", "top_p", "top_k", "frequency_penalty",
                  "presence_penalty", "seed", "stop", "response_format"}
OLLAMA_PARAMS = {"temperature", "max_tokens", "top_p", "top_k", "frequency_penalty",
                 "presence_penalty", "repeat_penalty", "repeat_last_n", "min_p",
                 "seed", "stop", "mirostat", "mirostat_tau", "mirostat_eta",
                 "num_ctx", "num_batch", "keep_alive", "tfs_z", "typical_p"}
ANTHROPIC_PARAMS = {"temperature", "max_tokens", "top_p", "top_k", "stop"}

PARAMS_BY_TYPE = {"openai": OPENAI_PARAMS, "ollama": OLLAMA_PARAMS, "anthropic": ANTHROPIC_PARAMS}


def _api_type(name: str) -> str:
    if name in _discovered:
        return _discovered[name].get("api_type", "openai")
    config = load_service_config(name)
    if config:
        return config.api_type
    return "openai"


def _adapt(messages: list[dict], params: dict, api_type: str, thinking: str | None = None) -> dict:
    allowed = PARAMS_BY_TYPE.get(api_type, OPENAI_PARAMS)
    payload = {k: v for k, v in params.items() if k in allowed}

    if api_type == "anthropic":
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        chat_msgs = [m for m in messages if m.get("role") != "system"]
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        payload["messages"] = chat_msgs
    else:
        payload["messages"] = messages

    # inject thinking/reasoning params based on api_type
    if thinking and thinking != "off":
        if api_type == "openai":
            payload["reasoning_effort"] = "high" if thinking == "deep" else "medium"
        elif api_type == "ollama":
            payload["think"] = True
        elif api_type == "anthropic":
            if thinking == "deep":
                payload["thinking"] = {"type": "enabled", "budget_tokens": payload.get("max_tokens", 8192)}
            else:
                payload["thinking"] = {"type": "enabled", "budget_tokens": min(payload.get("max_tokens", 4096), 4096)}

    return payload


class ChatRequest(BaseModel):
    service: str
    model: str
    messages: List[dict]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repeat_penalty: Optional[float] = None
    repeat_last_n: Optional[int] = None
    min_p: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    mirostat: Optional[int] = None
    mirostat_tau: Optional[float] = None
    mirostat_eta: Optional[float] = None
    num_ctx: Optional[int] = None
    num_batch: Optional[int] = None
    keep_alive: Optional[str] = None
    tfs_z: Optional[float] = None
    typical_p: Optional[float] = None
    response_format: Optional[dict] = None
    thinking: Optional[str] = None
    stream: Optional[bool] = None


@app.get("/api/models/all")
async def models_all():
    merged = []
    seen = set()
    sources = []
    # discovered services
    for name, d in _discovered.items():
        sources.append((name, f"http://{d['host']}:{d['port']}/v1", {}))
    # configured services
    for sname, cfg, _ in list_service_configs():
        if sname in _discovered:
            continue
        info = read_service_info(sname)
        if info and _pid_alive(info.get("pid", 0)):
            port = info.get("port")
            if port:
                sources.append((sname, f"http://127.0.0.1:{port}/v1", {}))
                continue
        if cfg.upstream.base_url:
            headers = {}
            if cfg.upstream.api_key_env:
                key = os.environ.get(cfg.upstream.api_key_env, "")
                if key:
                    headers["Authorization"] = f"Bearer {key}"
            sources.append((sname, cfg.upstream.base_url, headers))

    async with httpx.AsyncClient(timeout=10) as client:
        for sname, base, headers in sources:
            try:
                r = await client.get(f"{base}/models", headers=headers)
                r.raise_for_status()
                data = r.json()
                models_list = []
                if isinstance(data, dict) and "data" in data:
                    models_list = [m["id"] for m in data["data"]]
                elif isinstance(data, list):
                    models_list = [m.get("id", m.get("name", "?")) for m in data]
                for mid in models_list:
                    key = f"{sname}:{mid}"
                    if key not in seen:
                        seen.add(key)
                        merged.append({"id": mid, "service": sname})
            except Exception:
                pass
    return _filter_models(merged, _model_filter())


@app.get("/v1/health")
async def v1_health():
    return {"status": "ok"}


@app.get("/v1/models")
async def v1_models():
    merged = await models_all()
    seen = set()
    data = []
    for m in merged:
        mid = m["id"]
        if mid in seen:
            continue
        seen.add(mid)
        data.append({"id": mid, "object": "model"})
    return {"object": "list", "data": data}


@app.get("/api/proxy/models")
async def proxy_models(request: Request, base_url: str = Query(...)):
    if "api_key" in request.query_params:
        raise HTTPException(422, "api_key in query string is not accepted")
    headers = {}
    incoming = request.headers.get("authorization")
    if incoming and incoming.lower().startswith("bearer "):
        headers["Authorization"] = incoming
    base = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{base}/models", headers=headers)
            r.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"proxy_models upstream failure: {e}")
            raise HTTPException(502, "Failed to fetch models")
    data = r.json()
    if isinstance(data, dict) and "data" in data:
        return [{"id": m["id"]} for m in data["data"]]
    if isinstance(data, list):
        return [{"id": m.get("id", m.get("name", "?"))} for m in data]
    return []


@app.get("/api/models")
async def models(service: str = Query(...)):
    base, headers = _resolve(service)
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{base}/models", headers=headers)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Failed to fetch models: {e}")
    data = r.json()
    if isinstance(data, dict) and "data" in data:
        result = [{"id": m["id"]} for m in data["data"]]
    elif isinstance(data, list):
        result = [{"id": m.get("id", m.get("name", "?"))} for m in data]
    else:
        result = []
    return _filter_models(result, _model_filter())


class ManualChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str
    model: str
    messages: List[dict]
    api_type: Optional[str] = "openai"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    thinking: Optional[str] = None


@app.post("/api/proxy/chat")
async def proxy_chat(body: ManualChatRequest, request: Request):
    ip = _client_ip(request)
    blocked = _check_rate(ip)
    if blocked:
        return blocked
    headers = {"Content-Type": "application/json"}
    incoming = request.headers.get("authorization")
    if incoming and incoming.lower().startswith("bearer "):
        headers["Authorization"] = incoming

    raw_params = {}
    for key in ("temperature", "max_tokens", "top_p", "top_k", "frequency_penalty",
                "presence_penalty", "seed", "stop"):
        val = getattr(body, key, None)
        if val is not None:
            raw_params[key] = val

    at = body.api_type or "openai"
    payload = {"model": body.model, "stream": True, **_adapt(body.messages, raw_params, at, body.thinking)}
    payload["stream_options"] = {"include_usage": True}

    base = body.base_url.rstrip("/")

    from saturn import receipt as _receipt
    configured = {"model": body.model, **raw_params}
    system_prompt = next(
        (m.get("content") for m in body.messages if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str)),
        None,
    )

    async def generate():
        applied = {"max_tokens": body.max_tokens}
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
            async with client.stream("POST", f"{base}/chat/completions", json=payload, headers=headers) as r:
                if r.status_code != 200:
                    await r.aread()
                    yield f'data: {{"error": "upstream {r.status_code}"}}\n\n'
                    return
                async for line in r.aiter_lines():
                    if line.startswith("data:") and "[DONE]" in line:
                        yield _receipt.emit_meta_line(configured, applied, system_prompt, body.model)
                        yield line + "\n"
                        continue
                    _receipt.update_applied_from_chunk(applied, line)
                    if line:
                        yield line + "\n"
                    else:
                        yield "\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    ip = _client_ip(request)
    blocked = _check_rate(ip)
    if blocked:
        return blocked

    base, headers = _resolve(body.service)
    headers["Content-Type"] = "application/json"

    raw_params = {}
    for key in ("temperature", "max_tokens", "top_p", "top_k", "frequency_penalty",
                "presence_penalty", "repeat_penalty", "repeat_last_n", "min_p",
                "seed", "stop", "mirostat", "mirostat_tau", "mirostat_eta",
                "num_ctx", "num_batch", "keep_alive", "tfs_z", "typical_p",
                "response_format"):
        val = getattr(body, key, None)
        if val is not None:
            raw_params[key] = val

    at = _api_type(body.service)
    streaming = body.stream is not False
    payload = {"model": body.model, **_adapt(body.messages, raw_params, at, body.thinking)}
    payload["stream"] = streaming
    if streaming:
        payload["stream_options"] = {"include_usage": True}

    from saturn import receipt as _receipt
    configured = {"model": body.model, **raw_params}
    system_prompt = next(
        (m.get("content") for m in body.messages if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str)),
        None,
    )

    if not streaming:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
            r = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
            if r.status_code != 200:
                raise HTTPException(r.status_code, "upstream error")
            data = r.json()
            applied = {"max_tokens": body.max_tokens}
            if data.get("model"):
                applied["model"] = data["model"]
            if data.get("usage"):
                applied["usage"] = data["usage"]
            for c in data.get("choices") or []:
                if isinstance(c, dict) and c.get("finish_reason"):
                    applied["finish_reason"] = c["finish_reason"]
            data["saturn_meta"] = _receipt.build_meta(
                configured, applied, system_prompt, requested_model=body.model
            )
            return data

    sem = _ip_sem(ip)
    if sem.locked():
        return JSONResponse(status_code=429, content={"error": "Too many concurrent requests"},
                            headers={"Retry-After": "2"})

    async def generate():
        applied = {"max_tokens": body.max_tokens}
        async with sem:
            async with _global_semaphore:
                _ip_active[ip] = _ip_active.get(ip, 0) + 1
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
                        async with client.stream("POST", f"{base}/chat/completions", json=payload, headers=headers) as r:
                            if r.status_code != 200:
                                err = await r.aread()
                                yield f"data: {err.decode()}\n\n"
                                return
                            async for line in r.aiter_lines():
                                if line.startswith("data:") and "[DONE]" in line:
                                    yield _receipt.emit_meta_line(configured, applied, system_prompt, body.model)
                                    yield line + "\n"
                                    continue
                                _receipt.update_applied_from_chunk(applied, line)
                                if line:
                                    yield line + "\n"
                                else:
                                    yield "\n"
                finally:
                    _ip_active[ip] = max(0, _ip_active.get(ip, 1) - 1)

    rpm = _rpm_bucket(ip)
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-Saturn-Tokens-Remaining": str(int(rpm.remaining())),
            "Access-Control-Expose-Headers": "X-Saturn-Tokens-Remaining",
        },
    )


# --- Brutus API ---

class BrutusChat(BaseModel):
    messages: List[dict] = Field(..., max_length=200)
    model: Optional[str] = None
    conversation_id: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repeat_penalty: Optional[float] = None
    repeat_last_n: Optional[int] = None
    min_p: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    mirostat: Optional[int] = None
    mirostat_tau: Optional[float] = None
    mirostat_eta: Optional[float] = None
    num_ctx: Optional[int] = None
    num_batch: Optional[int] = None
    keep_alive: Optional[str] = None
    tfs_z: Optional[float] = None
    typical_p: Optional[float] = None
    response_format: Optional[dict] = None
    thinking: Optional[str] = None


@app.post("/api/system/chat")
async def brutus_chat(body: BrutusChat, request: Request, _=Depends(require_admin)):
    ip = _client_ip(request)
    blocked = _check_rate(ip)
    if blocked:
        return blocked
    t0 = time.time()
    skipped = []

    convo_id = request.headers.get("X-Saturn-Conversation-Id") or body.conversation_id

    candidates = []
    for name, d in _discovered.items():
        b = _breaker(name)
        if _breaker_open(b):
            skipped.append({"name": name, "reason": "circuit_breaker"})
            continue
        candidates.append({"name": name, "host": d["host"], "port": d["port"],
                           "priority": d.get("priority", 100),
                           "models": d.get("models", []) or []})
    disc_ports = {d["port"] for d in _discovered.values()}
    disc_bases = {n.split("-")[0] for n in _discovered}
    for sname, cfg, _ in list_service_configs():
        if sname in _discovered or sname in disc_bases:
            continue
        info = read_service_info(sname)
        if info and _pid_alive(info.get("pid", 0)):
            port = info.get("port")
            if port in disc_ports:
                continue
            b = _breaker(sname)
            if port and not _breaker_open(b):
                candidates.append({"name": sname, "host": "127.0.0.1", "port": port,
                                   "priority": cfg.priority, "models": []})
            elif port:
                skipped.append({"name": sname, "reason": "circuit_breaker"})

    requested_model = body.model
    if requested_model:
        has_known = any(c["models"] for c in candidates)
        affine = [c for c in candidates if (not c["models"]) or (requested_model in c["models"])]
        any_match = any(c["models"] and requested_model in c["models"] for c in candidates)
        if has_known and not any_match:
            raise HTTPException(502, f"No peer advertises requested model {requested_model!r}; refusing to silently route.")
        candidates = affine

    candidates.sort(key=lambda c: c["priority"])

    if convo_id and convo_id in _failover_state:
        sticky = _failover_state[convo_id]
        candidates.sort(key=lambda c: 0 if c["name"] == sticky else 1)
    elif not convo_id and _failover_hysteresis["name"] and (time.time() - _failover_hysteresis["at"]) < HYSTERESIS_S:
        h = _failover_hysteresis["name"]
        candidates.sort(key=lambda c: 0 if c["name"] == h else 1)

    if not candidates:
        raise HTTPException(502, "No healthy backends available. Run discovery first.")

    raw_params = {}
    for key in ("temperature", "max_tokens", "top_p", "top_k", "frequency_penalty",
                "presence_penalty", "repeat_penalty", "repeat_last_n", "min_p",
                "seed", "stop", "mirostat", "mirostat_tau", "mirostat_eta",
                "num_ctx", "num_batch", "keep_alive"):
        val = getattr(body, key, None)
        if val is not None:
            raw_params[key] = val

    events = []
    prev_name = None
    prev_reason = None

    chosen = None
    chosen_response = None
    chosen_client = None
    chosen_model = None

    for c in candidates:
        if prev_name:
            events.append({"from": _alias_peer(prev_name), "to": _alias_peer(c["name"]), "reason": prev_reason, "at": time.time()})
            prev_name = None
            prev_reason = None

        b = _breaker(c["name"])
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=0.5)) as hc:
                hr = await hc.get(f"http://{c['host']}:{c['port']}/v1/health")
                health_ok = hr.status_code == 200
        except Exception:
            health_ok = False
        if not health_ok:
            b["health_fails"] = b.get("health_fails", 0) + 1
            if b["health_fails"] >= 2:
                skipped.append({"name": c["name"], "reason": "health_timeout"})
                prev_name = c["name"]
                prev_reason = "health_timeout"
                continue
        else:
            b["health_fails"] = 0

        model = requested_model or (c["models"][0] if c["models"] else None)
        if not model:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=0.5)) as mc:
                    mr = await mc.get(f"http://{c['host']}:{c['port']}/v1/models")
                    data = mr.json()
                    if isinstance(data, dict) and "data" in data and data["data"]:
                        model = data["data"][0]["id"]
                    elif isinstance(data, list) and data:
                        model = data[0].get("id", data[0].get("name"))
            except Exception:
                pass
        if not model:
            skipped.append({"name": c["name"], "reason": "no_models"})
            prev_name = c["name"]
            prev_reason = "active_5xx"
            continue

        at = _api_type(c["name"])
        payload = {"model": model, "stream": True, **_adapt(body.messages, raw_params, at, body.thinking)}
        payload["stream_options"] = {"include_usage": True}

        client = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10))
        try:
            req = client.build_request("POST", f"http://{c['host']}:{c['port']}/v1/chat/completions",
                                       json=payload, headers={})
            resp = await client.send(req, stream=True)
        except Exception:
            try: await client.aclose()
            except Exception: pass
            _record_failure(c["name"])
            skipped.append({"name": c["name"], "reason": "error"})
            prev_name = c["name"]
            prev_reason = "active_5xx"
            continue
        if resp.status_code != 200:
            try: await resp.aclose()
            except Exception: pass
            try: await client.aclose()
            except Exception: pass
            _record_failure(c["name"])
            skipped.append({"name": c["name"], "reason": f"http_{resp.status_code}"})
            prev_name = c["name"]
            prev_reason = "active_5xx"
            continue

        _record_success(c["name"])
        if convo_id:
            _set_sticky(convo_id, c["name"], ip)
        else:
            _failover_hysteresis["name"] = c["name"]
            _failover_hysteresis["at"] = time.time()
        chosen = c
        chosen_response = resp
        chosen_client = client
        chosen_model = model
        break

    if not chosen:
        raise HTTPException(502, "All backends failed")

    from saturn import receipt as _receipt
    configured = {"model": chosen_model, **raw_params}
    system_prompt = next(
        (m.get("content") for m in body.messages if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str)),
        None,
    )
    latency = round((time.time() - t0) * 1000)
    _routing_log.append({
        "ts": time.time(),
        "service": chosen["name"],
        "model": chosen_model,
        "skipped": [s["name"] for s in skipped],
        "latency_ms": latency,
    })

    async def generate():
        applied = {"max_tokens": body.max_tokens}
        try:
            async for line in chosen_response.aiter_lines():
                if line.startswith("data:") and "[DONE]" in line:
                    meta = _receipt.build_meta(configured, applied, system_prompt, requested_model=chosen_model)
                    meta.setdefault("routing", {})["events"] = events
                    meta["routing"]["service"] = _alias_peer(chosen["name"])
                    yield f"data: {json.dumps({'saturn_meta': meta})}\n\n"
                    yield line + "\n"
                    continue
                _receipt.update_applied_from_chunk(applied, line)
                if line:
                    yield line + "\n"
                else:
                    yield "\n"
        finally:
            try: await chosen_response.aclose()
            except Exception: pass
            try: await chosen_client.aclose()
            except Exception: pass

    skipped_names = ",".join(s["name"] for s in skipped) if skipped else ""
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-Saturn-Service": chosen["name"],
            "X-Saturn-Model": chosen_model,
            "X-Saturn-Skipped": skipped_names,
            "X-Saturn-Latency": str(latency),
            "Access-Control-Expose-Headers": "X-Saturn-Service, X-Saturn-Model, X-Saturn-Skipped, X-Saturn-Latency",
        },
    )


@app.get("/api/system/status")
async def brutus_status(_=Depends(require_admin)):
    backends = []
    for name, d in _discovered.items():
        b = _breaker(name)
        is_open = _breaker_open(b)
        cooldown = 0
        if is_open:
            cooldown = max(0, BREAKER_COOLDOWN - (time.time() - b["opened_at"]))
        backends.append({
            "name": name,
            "host": d["host"],
            "port": d["port"],
            "priority": d.get("priority", 100),
            "models": d.get("models", []),
            "source": "discovered",
            "healthy": not is_open,
            "breaker": {"failures": b["failures"], "open": is_open, "cooldown": round(cooldown)},
        })
    discovered_ports = {d["port"] for d in _discovered.values()}
    discovered_bases = {n.split("-")[0] for n in _discovered}
    for sname, cfg, _ in list_service_configs():
        if sname in _discovered:
            continue
        info = read_service_info(sname)
        running = info and _pid_alive(info.get("pid", 0))
        if not running:
            continue
        # skip if this service's port or base name matches a discovered entry
        if info.get("port") in discovered_ports or sname in discovered_bases:
            continue
        b = _breaker(sname)
        is_open = _breaker_open(b)
        cooldown = 0
        if is_open:
            cooldown = max(0, BREAKER_COOLDOWN - (time.time() - b["opened_at"]))
        backends.append({
            "name": sname,
            "host": "127.0.0.1",
            "port": info.get("port"),
            "priority": cfg.priority,
            "models": [],
            "source": "configured",
            "healthy": not is_open,
            "breaker": {"failures": b["failures"], "open": is_open, "cooldown": round(cooldown)},
        })
    backends.sort(key=lambda b: b["priority"])

    running = _tunnel_proc is not None and _tunnel_proc.returncode is None
    return {
        "backends": backends,
        "tunnel": {"status": "running" if running else "stopped", "url": _tunnel_url if running else None},
        "routing_log": list(_routing_log)[-20:],
    }


@app.get("/api/system/url")
async def brutus_url():
    global _tunnel_url
    if _tunnel_url:
        return {"url": _tunnel_url, "mode": "tunnel"}
    ip = _lan_ip()
    # infer port from uvicorn — default 3000
    return {"url": f"http://{ip}:3000" if ip else None, "mode": "lan"}


@app.get("/api/system/tunnel/status")
async def brutus_tunnel_status():
    global _tunnel_proc, _tunnel_url
    running = _tunnel_proc is not None and _tunnel_proc.returncode is None
    return {"url": _tunnel_url, "status": "running" if running else "stopped"}


async def _drain(stream):
    try:
        while await stream.readline():
            pass
    except Exception:
        pass


async def _kill_tunnel():
    global _tunnel_proc, _tunnel_url
    if _tunnel_proc:
        _tunnel_proc.terminate()
        try:
            await asyncio.wait_for(_tunnel_proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            _tunnel_proc.kill()
            await _tunnel_proc.wait()
        _tunnel_proc = None
    _tunnel_url = None


@app.post("/api/system/tunnel/start")
async def brutus_tunnel_start(_=Depends(require_admin)):
    global _tunnel_proc, _tunnel_url
    if _tunnel_proc and _tunnel_proc.returncode is None and _tunnel_url:
        return {"url": _tunnel_url, "status": "running"}

    # clean up any stale process before spawning
    await _kill_tunnel()

    try:
        _tunnel_proc = await asyncio.create_subprocess_exec(
            "cloudflared", "tunnel", "--url", "http://localhost:3000",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise HTTPException(500, "cloudflared not installed")

    # read stderr until the tunnel is actually connected (not just URL assigned)
    buf = b""
    url = None
    timed_out = False
    try:
        async with asyncio.timeout(30):
            while True:
                line = await _tunnel_proc.stderr.readline()
                if not line:
                    break
                buf += line
                if not url:
                    m = re.search(rb"https://[a-z0-9-]+\.trycloudflare\.com", line)
                    if m:
                        url = m.group(0).decode()
                if url and b"Registered tunnel connection" in line:
                    break
    except asyncio.TimeoutError:
        timed_out = True
    except Exception:
        await _kill_tunnel()
        return {"error": "Tunnel failed to start", "log": buf.decode(errors="replace")}

    if timed_out and not url:
        await _kill_tunnel()
        return {"error": "Tunnel timed out — is cloudflared installed?"}

    if not url:
        await _kill_tunnel()
        return {"error": "Tunnel failed to start", "log": buf.decode(errors="replace")}

    # drain remaining stderr in background to prevent pipe buffer deadlock
    asyncio.create_task(_drain(_tunnel_proc.stderr))

    # wait for Cloudflare DNS to propagate the new subdomain.
    # system resolver caches NXDOMAIN aggressively, so query authoritative DNS
    # directly via dig to avoid poisoning the local cache.
    host = url.replace("https://", "")
    for _ in range(15):
        try:
            probe = await asyncio.create_subprocess_exec(
                "dig", "+short", host, "@1.1.1.1",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            out, _ = await asyncio.wait_for(probe.communicate(), timeout=3)
            if out.strip():
                break
        except Exception:
            pass
        await asyncio.sleep(1)

    _tunnel_url = url
    return {"url": _tunnel_url, "status": "running"}


@app.post("/api/system/tunnel/stop")
async def brutus_tunnel_stop(_=Depends(require_admin)):
    await _kill_tunnel()
    return {"status": "stopped"}


# --- MCP API ---

class MCPServerAdd(BaseModel):
    url: str
    name: str
    auth_token: Optional[str] = None


class MCPToolCall(BaseModel):
    server: str
    tool: str
    arguments: dict = {}


@app.get("/api/mcp/servers")
async def mcp_servers(_=Depends(require_admin)):
    return mcp_manager.configured()


@app.post("/api/mcp/servers")
async def mcp_add(body: MCPServerAdd, _=Depends(require_admin)):
    mcp_manager.add(body.name, body.url, body.auth_token)
    try:
        await mcp_manager.refresh(body.name)
    except Exception as e:
        logger.warning(f"MCP refresh failed for {body.name}: {e}")
        return {"added": True, "refreshed": False, "error": str(e)}
    return {"added": True, "refreshed": True}


@app.delete("/api/mcp/servers/{name}")
async def mcp_remove(name: str, _=Depends(require_admin)):
    if not mcp_manager.remove(name):
        raise HTTPException(404, f"MCP server '{name}' not found")
    return {"deleted": True, "name": name}


@app.get("/api/mcp/tools")
async def mcp_tools():
    return mcp_manager.tools()


@app.post("/api/mcp/tools/call")
async def mcp_call(body: MCPToolCall):
    return await mcp_manager.call(body.server, body.tool, body.arguments)


# --- Rate Limit & Usage API (SAT-2n8.1, SAT-2n8.2) ---

@app.get("/api/rate-limit/status")
async def rate_limit_status(request: Request):
    ip = _client_ip(request)
    rpm = _rpm_bucket(ip)
    tpm = _tpm_bucket(ip)
    return {
        "rpm": {"remaining": int(rpm.remaining()), "limit": RATE_RPM},
        "tpm": {"remaining": int(tpm.remaining()), "limit": RATE_TPM},
        "concurrent": {"active": _ip_active.get(ip, 0), "limit": RATE_CONCURRENT_PER_IP},
        "global_concurrent": {"limit": RATE_CONCURRENT_GLOBAL},
    }


@app.get("/api/usage")
async def usage(request: Request, user_id: str = Query(default=""), _=Depends(require_admin)):
    ip = user_id or _client_ip(request)
    period = time.strftime("%Y-%m-%d")
    conn = _db()
    row = conn.execute(
        "SELECT tokens_in, tokens_out, requests FROM usage WHERE user_id=? AND period=?",
        (ip, period)
    ).fetchone()
    conn.close()
    if not row:
        return {"user_id": ip, "period": period, "tokens_in": 0, "tokens_out": 0, "requests": 0}
    return {"user_id": ip, "period": period, "tokens_in": row[0], "tokens_out": row[1], "requests": row[2]}


class UsageReport(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0


@app.post("/api/usage/report")
async def report_usage(body: UsageReport, request: Request):
    ip = _client_ip(request)
    if body.tokens_in > 0 or body.tokens_out > 0:
        _record_usage(ip, body.tokens_in, body.tokens_out)
        _tpm_bucket(ip).consume(body.tokens_in + body.tokens_out)
    return {"ok": True}


@app.get("/api/usage/history")
async def usage_history(request: Request, user_id: str = Query(default=""), days: int = Query(default=7), _=Depends(require_admin)):
    ip = user_id or _client_ip(request)
    conn = _db()
    rows = conn.execute(
        "SELECT period, tokens_in, tokens_out, requests FROM usage WHERE user_id=? ORDER BY period DESC LIMIT ?",
        (ip, days)
    ).fetchall()
    conn.close()
    return [{"period": r[0], "tokens_in": r[1], "tokens_out": r[2], "requests": r[3]} for r in rows]


# --- Admin Config API ---

class AdminConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_filter: Optional[str] = None
    max_budget: Optional[float] = None
    budget_duration: Optional[str] = None
    admin_session_ttl_s: Optional[int] = None
    admin_token_env: Optional[str] = None
    runner_token_env: Optional[str] = None
    admin_password_env: Optional[str] = None
    bind_host: Optional[str] = None
    runner_bind_host: Optional[str] = None
    trusted_proxies: Optional[List[str]] = None
    cors_origins: Optional[List[str]] = None
    rate_rpm: Optional[int] = None
    rate_tpm: Optional[int] = None
    rate_concurrent_per_ip: Optional[int] = None
    max_budget_usd: Optional[float] = None
    budget_period: Optional[str] = None
    per_ip_max_budget_usd: Optional[float] = None
    public_routes: Optional[List[str]] = None
    require_auth_on_v1: Optional[bool] = None
    proxy_models_method: Optional[str] = None
    redact_proxy_keys_in_logs: Optional[bool] = None
    mcp_allowed_urls: Optional[List[str]] = None
    mcp_auth_token_envs: Optional[dict] = None
    trust_mode: Optional[str] = None
    trusted_node_ids: Optional[List[str]] = None
    beacon_max_budget_usd: Optional[float] = None


def validate_admin_config(cfg: dict) -> List[str]:
    import ipaddress
    import uuid as _uuid
    errs: List[str] = []
    dev_mode = os.environ.get("SATURN_DEV_MODE") == "1"
    if "trusted_proxies" in cfg and cfg["trusted_proxies"] is not None:
        for p in cfg["trusted_proxies"]:
            try:
                ipaddress.ip_network(p, strict=False)
            except Exception:
                errs.append(f"trusted_proxies entry invalid CIDR/IP: {p!r}")
    for hostkey in ("bind_host", "runner_bind_host"):
        if hostkey in cfg and cfg[hostkey] is not None:
            try:
                ipaddress.ip_address(cfg[hostkey])
            except Exception:
                errs.append(f"{hostkey} invalid IP literal: {cfg[hostkey]!r}")
    if "admin_session_ttl_s" in cfg and cfg["admin_session_ttl_s"] is not None:
        v = cfg["admin_session_ttl_s"]
        if not isinstance(v, int) or v < 60:
            errs.append("admin_session_ttl_s must be int >= 60")
    for key in ("rate_rpm", "rate_tpm", "rate_concurrent_per_ip"):
        if key in cfg and cfg[key] is not None:
            v = cfg[key]
            if not isinstance(v, int) or v < 1:
                errs.append(f"{key} must be int >= 1")
    if "trusted_node_ids" in cfg and cfg["trusted_node_ids"] is not None:
        for nid in cfg["trusted_node_ids"]:
            try:
                _uuid.UUID(nid)
            except Exception:
                errs.append(f"trusted_node_ids entry invalid UUID: {nid!r}")
    if "trust_mode" in cfg and cfg["trust_mode"] is not None:
        m = cfg["trust_mode"]
        if m not in ("tofu", "allowlist", "open"):
            errs.append("trust_mode must be one of tofu|allowlist|open")
        elif m == "open" and not dev_mode:
            errs.append("trust_mode=open requires SATURN_DEV_MODE=1")
    if "cors_origins" in cfg and cfg["cors_origins"] is not None:
        for o in cfg["cors_origins"]:
            if "*" in str(o) and not dev_mode:
                errs.append("cors_origins wildcard requires SATURN_DEV_MODE=1")
    if "proxy_models_method" in cfg and cfg["proxy_models_method"] is not None:
        if cfg["proxy_models_method"] not in ("GET", "POST"):
            errs.append("proxy_models_method must be GET|POST")
    if "budget_period" in cfg and cfg["budget_period"] is not None:
        if cfg["budget_period"] not in ("monthly", "weekly", "daily"):
            errs.append("budget_period must be monthly|weekly|daily")
    return errs


def _apply_trust_policy(cfg: dict) -> None:
    from saturn import discovery as _disc
    mode = cfg.get("trust_mode") or "tofu"
    allow = cfg.get("trusted_node_ids") or []
    _disc.set_trust_policy(mode, allow)


def _reclassify_discovered() -> None:
    from saturn import discovery as _disc
    drop = []
    for name, d in list(_discovered.items()):
        nid = d.get("node_id", "")
        s = _disc.SaturnService(name=name, host=d.get("host", ""), port=d.get("port", 0), node_id=nid)
        verdict = _disc._classify_trust(s)
        if _disc._trust_mode != "open" and verdict not in _disc._SELECTABLE:
            drop.append(name)
    for name in drop:
        _discovered.pop(name, None)


def apply_admin_config(cfg: dict) -> None:
    global RATE_RPM, RATE_TPM, RATE_CONCURRENT_PER_IP
    if isinstance(cfg.get("rate_rpm"), int):
        RATE_RPM = cfg["rate_rpm"]
        _rpm_buckets.clear()
    if isinstance(cfg.get("rate_tpm"), int):
        RATE_TPM = cfg["rate_tpm"]
        _tpm_buckets.clear()
    if isinstance(cfg.get("rate_concurrent_per_ip"), int):
        RATE_CONCURRENT_PER_IP = cfg["rate_concurrent_per_ip"]
        _ip_semaphores.clear()
    _apply_trust_policy(cfg)
    _set_trusted_proxies(cfg.get("trusted_proxies") or [])
    _reclassify_discovered()


@app.get("/api/admin/config")
async def get_admin_config(_=Depends(require_admin)):
    return _load_admin_config()


@app.post("/api/admin/config")
async def set_admin_config(body: AdminConfig, _=Depends(require_admin)):
    incoming = body.model_dump(exclude_unset=True)
    cfg = _load_admin_config()
    merged = {**cfg, **incoming}
    errs = validate_admin_config(merged)
    if errs:
        raise HTTPException(422, {"errors": errs})
    cfg.update(incoming)
    _save_admin_config(cfg)
    apply_admin_config(cfg)
    return cfg


@app.post("/api/admin/config/validate")
async def validate_admin_config_route(body: AdminConfig, _=Depends(require_admin)):
    incoming = body.model_dump(exclude_unset=True)
    cfg = _load_admin_config()
    merged = {**cfg, **incoming}
    errs = validate_admin_config(merged)
    return {"ok": not errs, "errors": errs}


class _ServiceTest(BaseModel):
    base_url: str
    api_key_env: Optional[str] = None
    api_type: Optional[str] = "openai"


@app.post("/api/services/test")
async def test_service(body: _ServiceTest, _=Depends(require_admin)):
    base = (body.base_url or "").strip().rstrip("/")
    if not base:
        raise HTTPException(422, "base_url required")
    if not (base.startswith("http://") or base.startswith("https://")):
        raise HTTPException(422, "base_url must start with http:// or https://")
    headers = {}
    if body.api_key_env:
        key = os.environ.get(body.api_key_env, "")
        if not key:
            return {"ok": False, "error": f"env var {body.api_key_env!r} is empty or unset"}
        headers["Authorization"] = f"Bearer {key}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=4)) as c:
            r = await c.get(f"{base}/models", headers=headers)
    except httpx.ConnectError as e:
        return {"ok": False, "error": f"connection failed: {e}"}
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"request failed: {e}"}
    if r.status_code == 401 or r.status_code == 403:
        return {"ok": False, "status": r.status_code, "error": "auth rejected — check api_key_env"}
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code, "error": f"upstream returned {r.status_code}"}
    try:
        data = r.json()
    except Exception:
        return {"ok": False, "error": "upstream did not return JSON"}
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        count = len(data["data"])
    elif isinstance(data, list):
        count = len(data)
    else:
        count = 0
    return {"ok": True, "status": 200, "models": count}


# --- Service identity (TOFU + allowlist) admin API ---

from saturn.mdns import known_nodes as _known_nodes


class AttestBody(BaseModel):
    service: str
    node_id: str
    host: Optional[str] = ""


class ForgetBody(BaseModel):
    service: str


@app.get("/api/admin/known-nodes")
async def get_known_nodes(_=Depends(require_admin)):
    return _known_nodes.load()


@app.post("/api/admin/known-nodes/attest")
async def attest_known_node(body: AttestBody, _=Depends(require_admin)):
    import uuid as _uuid
    try:
        _uuid.UUID(body.node_id)
    except (ValueError, TypeError):
        raise HTTPException(422, "node_id must be a UUID")
    _known_nodes.attest(body.service, body.node_id, body.host or "")
    _reclassify_discovered()
    return _known_nodes.load()


@app.post("/api/admin/known-nodes/forget")
async def forget_known_node(body: ForgetBody, _=Depends(require_admin)):
    _known_nodes.forget(body.service)
    _reclassify_discovered()
    return _known_nodes.load()



@app.get("/admin/configure")
@app.get("/configure")
@app.get("/admin/services")
async def admin_configure_route(_=Depends(require_admin)):
    import html as _html
    import re as _re
    from fastapi.responses import HTMLResponse
    index = WEB_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(404, "Not found")
    text = index.read_text()
    text = text.replace(
        'class="hidden admin-configure-page"',
        'class="admin-configure-page"',
    )
    text = text.replace("<head>", '<head><base href="/">', 1)
    cfg = _load_admin_config()
    for name in AdminConfig.model_fields:
        if name not in cfg or cfg[name] is None:
            continue
        v = cfg[name]
        if isinstance(v, bool):
            if v:
                text = _re.sub(
                    r'(<input(?:[^>]*?)\sid="ac-' + _re.escape(name) + r'"(?:[^>]*?)\stype="checkbox")(?![^>]*\schecked)',
                    lambda mm: mm.group(1) + ' checked',
                    text,
                )
            continue
        if isinstance(v, list):
            rendered = ",".join(str(x) for x in v)
        elif isinstance(v, dict):
            rendered = json.dumps(v)
        else:
            rendered = str(v)
        escaped = _html.escape(rendered, quote=True)
        select_pat = _re.search(
            r'(<select(?:[^>]*?)\sid="ac-' + _re.escape(name) + r'"[^>]*>)(.*?)(</select>)',
            text, _re.DOTALL,
        )
        if select_pat:
            opts = _re.sub(
                r'\sselected\b', '', select_pat.group(2),
            )
            opts = _re.sub(
                r'(<option\s+value="' + _re.escape(escaped) + r'")(?![^>]*\sselected)',
                lambda mm: mm.group(1) + ' selected',
                opts,
            )
            text = text.replace(
                select_pat.group(0),
                select_pat.group(1) + opts + select_pat.group(3),
                1,
            )
            continue
        text = _re.sub(
            r'(<input(?:[^>]*?)\sid="ac-' + _re.escape(name) + r'")(?![^>]*\svalue=)',
            lambda mm, e=escaped: mm.group(1) + f' value="{e}"',
            text,
        )
    return HTMLResponse(text)


# --- Static files ---

@app.get("/{path:path}")
async def static(path: str = ""):
    if path == "" or path == "/":
        path = "index.html"
    file = WEB_DIR / path
    if file.is_file():
        return FileResponse(file)
    # SPA fallback
    index = WEB_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(404, "Not found")


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
    entries = cfg.get("trusted_proxies") or []
    if not entries:
        return []
    bad, good = [], 0
    for p in entries:
        try:
            ipaddress.ip_network(p, strict=False)
            good += 1
        except Exception:
            bad.append(p)
    for p in bad:
        logger.warning(f"trusted_proxies skipping invalid CIDR {p!r}")
    if bad and good == 0:
        return [f"trusted_proxies all entries invalid (CIDR parse failed): {bad!r}"]
    return []


def _check_cors_no_wildcard(cfg: dict) -> List[str]:
    if os.environ.get("SATURN_DEV_MODE") == "1":
        return []
    errs: List[str] = []
    for o in cfg.get("cors_origins") or []:
        if "*" in str(o):
            errs.append('cors_origins wildcard "*" forbidden; set SATURN_DEV_MODE=1 to allow')
    return errs


def _run_boot_validators() -> List[str]:
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


def main(host: str = "0.0.0.0", port: int = 3000):
    errs = _run_boot_validators()
    if errs:
        for e in errs:
            print(f"saturn: config error: {e}", file=sys.stderr)
        sys.stderr.flush()
        if os.environ.get("SATURN_DEV_MODE") != "1":
            sys.exit(1)
    print(f"Saturn Web UI -> http://localhost:{port}")
    uvicorn.run(app, host=host, port=port, forwarded_allow_ips=[])
