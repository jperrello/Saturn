import os
import sys
import re
import subprocess
import signal
import time
import asyncio
import logging
import socket
from pathlib import Path
from typing import Optional, List
from dataclasses import asdict

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

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

WEB_DIR = Path(__file__).parent.parent / "Web-UI"

app = FastAPI(title="Saturn Web UI")


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
_tunnel_proc: Optional[subprocess.Popen] = None
_tunnel_url: Optional[str] = None

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


# --- API Routes ---

@app.get("/api/services")
async def services():
    configs = list_service_configs()
    return [_config_to_dict(name, cfg, builtin) for name, cfg, builtin in configs]


@app.post("/api/services")
async def create(body: ServiceCreate):
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
async def start(name: str, body: ServiceStart = None):
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

    # wait briefly for service info file to appear
    for _ in range(20):
        time.sleep(0.25)
        info = read_service_info(name)
        if info and _pid_alive(info.get("pid", 0)):
            return {"started": True, "pid": info["pid"], "port": info.get("port")}

    return {"started": True, "pid": proc.pid, "port": None}


@app.post("/api/services/{name}/stop")
async def stop(name: str):
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
    return {"stopped": True, "name": name}


@app.delete("/api/services/{name}")
async def delete(name: str):
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


class ChatRequest(BaseModel):
    service: str
    model: str
    messages: List[dict]


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
    return merged


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
    # OpenAI format: { data: [{ id: ... }, ...] }
    if isinstance(data, dict) and "data" in data:
        return [{"id": m["id"]} for m in data["data"]]
    if isinstance(data, list):
        return [{"id": m.get("id", m.get("name", "?"))} for m in data]
    return []


@app.post("/api/chat")
async def chat(body: ChatRequest):
    base, headers = _resolve(body.service)
    headers["Content-Type"] = "application/json"

    payload = {
        "model": body.model,
        "messages": body.messages,
        "stream": True,
    }

    async def generate():
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

    return StreamingResponse(generate(), media_type="text/event-stream")


# --- Brutus API ---

class BrutusChat(BaseModel):
    messages: List[dict]


@app.post("/api/brutus/chat")
async def brutus_chat(body: BrutusChat):
    # gather candidates from discovered + running configured services
    candidates = []
    for name, d in _discovered.items():
        if not _breaker_open(_breaker(name)):
            candidates.append({"name": name, "host": d["host"], "port": d["port"], "priority": d.get("priority", 100), "models": d.get("models", [])})
    for sname, cfg, _ in list_service_configs():
        if sname in _discovered:
            continue
        info = read_service_info(sname)
        if info and _pid_alive(info.get("pid", 0)):
            port = info.get("port")
            if port and not _breaker_open(_breaker(sname)):
                candidates.append({"name": sname, "host": "127.0.0.1", "port": port, "priority": cfg.priority, "models": []})

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
                    pass
            if not model:
                continue

            try:
                payload = {"model": model, "messages": body.messages, "stream": True}

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

                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                    headers={
                        "X-Brutus-Service": c["name"],
                        "X-Brutus-Model": model,
                        "Access-Control-Expose-Headers": "X-Brutus-Service, X-Brutus-Model",
                    },
                )
            except Exception:
                _record_failure(c["name"])
                continue

    raise HTTPException(502, "All backends failed")


@app.get("/api/brutus/url")
async def brutus_url():
    global _tunnel_url
    if _tunnel_url:
        return {"url": _tunnel_url, "mode": "tunnel"}
    ip = _lan_ip()
    # infer port from uvicorn — default 3000
    return {"url": f"http://{ip}:3000" if ip else None, "mode": "lan"}


@app.get("/api/brutus/tunnel/status")
async def brutus_tunnel_status():
    global _tunnel_proc, _tunnel_url
    running = _tunnel_proc is not None and _tunnel_proc.poll() is None
    return {"url": _tunnel_url, "status": "running" if running else "stopped"}


@app.post("/api/brutus/tunnel/start")
async def brutus_tunnel_start():
    global _tunnel_proc, _tunnel_url
    if _tunnel_proc and _tunnel_proc.poll() is None and _tunnel_url:
        return {"url": _tunnel_url, "status": "running"}

    try:
        _tunnel_proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:3000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise HTTPException(500, "cloudflared not installed")

    # read stderr until we find the URL (up to 30s)
    deadline = time.time() + 30
    buf = b""
    while time.time() < deadline:
        try:
            chunk = _tunnel_proc.stderr.read(4096)
            if not chunk:
                break
            buf += chunk
            m = re.search(rb"https://[a-z0-9-]+\.trycloudflare\.com", buf)
            if m:
                _tunnel_url = m.group(0).decode()
                return {"url": _tunnel_url, "status": "running"}
        except Exception:
            break

    return {"error": "Tunnel failed to start", "log": buf.decode(errors="replace")}


@app.post("/api/brutus/tunnel/stop")
async def brutus_tunnel_stop():
    global _tunnel_proc, _tunnel_url
    if _tunnel_proc:
        _tunnel_proc.terminate()
        _tunnel_proc = None
    _tunnel_url = None
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
async def mcp_servers():
    return mcp_manager.configured()


@app.post("/api/mcp/servers")
async def mcp_add(body: MCPServerAdd):
    mcp_manager.add(body.name, body.url, body.auth_token)
    try:
        await mcp_manager.refresh(body.name)
    except Exception as e:
        logger.warning(f"MCP refresh failed for {body.name}: {e}")
        return {"added": True, "refreshed": False, "error": str(e)}
    return {"added": True, "refreshed": True}


@app.delete("/api/mcp/servers/{name}")
async def mcp_remove(name: str):
    if not mcp_manager.remove(name):
        raise HTTPException(404, f"MCP server '{name}' not found")
    return {"deleted": True, "name": name}


@app.get("/api/mcp/tools")
async def mcp_tools():
    return mcp_manager.tools()


@app.post("/api/mcp/tools/call")
async def mcp_call(body: MCPToolCall):
    return await mcp_manager.call(body.server, body.tool, body.arguments)


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
