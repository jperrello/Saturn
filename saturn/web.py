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
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List
from dataclasses import asdict

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

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


# --- API Models ---

class ServiceCreate(BaseModel):
    name: str
    deployment: str = "cloud"
    api_type: str = "openai"
    priority: int = 50
    base_url: str = ""
    api_key_env: Optional[str] = None
    port: int = 0
    beacon_enabled: bool = False
    beacon_provider: Optional[str] = None
    rotation_interval: int = 300
    expiration_interval: int = 600


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

_breakers: dict[str, dict] = {}  # name -> {failures, opened_at}
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


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


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


def _load_admin_config() -> dict:
    global _admin_config
    config_path = Path(__file__).parent.parent / "data" / "admin_config.json"
    if config_path.exists():
        try:
            _admin_config = json.loads(config_path.read_text())
        except Exception:
            _admin_config = {}
    return _admin_config


def _save_admin_config(config: dict):
    global _admin_config
    _admin_config = config
    config_path = Path(__file__).parent.parent / "data" / "admin_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))


def _model_filter() -> str:
    cfg = _load_admin_config()
    return cfg.get("model_filter", MODEL_FILTER)


ADMIN_PASSWORD = os.environ.get("SATURN_ADMIN_PASSWORD", "saturn")
ADMIN_TOKEN_ENV = os.environ.get("SATURN_ADMIN_TOKEN_ENV", "SATURN_ADMIN_TOKEN")


def require_admin(authorization: Optional[str] = Header(default=None)):
    import hmac
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
    return {"ok": True}


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

    ensure_services_dir()
    lines = [
        f'name = "{body.name}"',
        f'deployment = "{body.deployment}"',
        f'api_type = "{body.api_type}"',
        f'priority = {body.priority}',
        "",
        "[upstream]",
        f'base_url = "{body.base_url}"',
    ]
    if body.api_key_env:
        lines.append(f'api_key_env = "{body.api_key_env}"')
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
async def api_discover():
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
        }
        result.append(entry)
        _discovered[s.name] = entry
    return result


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

    async def generate():
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
            async with client.stream("POST", f"{base}/chat/completions", json=payload, headers=headers) as r:
                if r.status_code != 200:
                    await r.aread()
                    yield f'data: {{"error": "upstream {r.status_code}"}}\n\n'
                    return
                async for line in r.aiter_lines():
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
    payload = {"model": body.model, "stream": True, **_adapt(body.messages, raw_params, at, body.thinking)}
    payload["stream_options"] = {"include_usage": True}

    sem = _ip_sem(ip)
    if sem.locked():
        return JSONResponse(status_code=429, content={"error": "Too many concurrent requests"},
                            headers={"Retry-After": "2"})

    async def generate():
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


@app.post("/api/system/chat")
async def brutus_chat(body: BrutusChat, request: Request):
    ip = _client_ip(request)
    blocked = _check_rate(ip)
    if blocked:
        return blocked
    t0 = time.time()
    skipped = []

    # gather candidates from discovered + running configured services
    candidates = []
    for name, d in _discovered.items():
        b = _breaker(name)
        if _breaker_open(b):
            skipped.append({"name": name, "reason": "circuit_breaker"})
            continue
        candidates.append({"name": name, "host": d["host"], "port": d["port"], "priority": d.get("priority", 100), "models": d.get("models", [])})
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
                candidates.append({"name": sname, "host": "127.0.0.1", "port": port, "priority": cfg.priority, "models": []})
            elif port:
                skipped.append({"name": sname, "reason": "circuit_breaker"})

    candidates.sort(key=lambda c: c["priority"])

    if not candidates:
        raise HTTPException(502, "No healthy backends available. Run discovery first.")

    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
        for c in candidates:
            base = f"http://{c['host']}:{c['port']}/v1"
            model = c["models"][0] if c["models"] else None
            if not model:
                try:
                    r = await client.get(f"{base}/models", timeout=5)
                    data = r.json()
                    if isinstance(data, dict) and "data" in data:
                        model = data["data"][0]["id"] if data["data"] else None
                    elif isinstance(data, list) and data:
                        model = data[0].get("id", data[0].get("name"))
                except Exception:
                    skipped.append({"name": c["name"], "reason": "no_models"})
                    continue
            if not model:
                skipped.append({"name": c["name"], "reason": "no_models"})
                continue

            try:
                latency = round((time.time() - t0) * 1000)
                raw_params = {}
                for key in ("temperature", "max_tokens", "top_p", "top_k", "frequency_penalty",
                            "presence_penalty", "repeat_penalty", "repeat_last_n", "min_p",
                            "seed", "stop", "mirostat", "mirostat_tau", "mirostat_eta",
                            "num_ctx", "num_batch", "keep_alive"):
                    val = getattr(body, key, None)
                    if val is not None:
                        raw_params[key] = val

                at = _api_type(c["name"])
                payload = {"model": model, "stream": True, **_adapt(body.messages, raw_params, at, body.thinking)}
                payload["stream_options"] = {"include_usage": True}

                _routing_log.append({
                    "ts": time.time(),
                    "service": c["name"],
                    "model": model,
                    "skipped": [s["name"] for s in skipped],
                    "latency_ms": latency,
                })

                async def generate(base_url=base, pay=payload, hdrs={}, svc_name=c["name"], mdl=model):
                    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as c2:
                        async with c2.stream("POST", f"{base_url}/chat/completions", json=pay, headers=hdrs) as r:
                            if r.status_code != 200:
                                _record_failure(svc_name)
                                err = await r.aread()
                                yield f"data: {err.decode()}\n\n"
                                return
                            _record_success(svc_name)
                            # emit metadata as first event
                            yield f"data: {{}}\n\n"
                            async for line in r.aiter_lines():
                                if line:
                                    yield line + "\n"
                                else:
                                    yield "\n"

                skipped_names = ",".join(s["name"] for s in skipped) if skipped else ""
                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                    headers={
                        "X-Saturn-Service": c["name"],
                        "X-Saturn-Model": model,
                        "X-Saturn-Skipped": skipped_names,
                        "X-Saturn-Latency": str(latency),
                        "Access-Control-Expose-Headers": "X-Saturn-Service, X-Saturn-Model, X-Saturn-Skipped, X-Saturn-Latency",
                    },
                )
            except Exception:
                _record_failure(c["name"])
                skipped.append({"name": c["name"], "reason": "error"})
                continue

    raise HTTPException(502, "All backends failed")


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
    model_filter: Optional[str] = None
    max_budget: Optional[float] = None
    budget_duration: Optional[str] = None


@app.get("/api/admin/config")
async def get_admin_config(_=Depends(require_admin)):
    return _load_admin_config()


@app.post("/api/admin/config")
async def set_admin_config(body: AdminConfig, _=Depends(require_admin)):
    cfg = _load_admin_config()
    if body.model_filter is not None:
        cfg["model_filter"] = body.model_filter
    if body.max_budget is not None:
        cfg["max_budget"] = body.max_budget
    if body.budget_duration is not None:
        cfg["budget_duration"] = body.budget_duration
    _save_admin_config(cfg)
    return cfg


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


def main(host: str = "0.0.0.0", port: int = 3000):
    print(f"Saturn Web UI -> http://localhost:{port}")
    uvicorn.run(app, host=host, port=port)
