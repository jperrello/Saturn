import os
import sys
import subprocess
import signal
import time
import asyncio
import logging
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
