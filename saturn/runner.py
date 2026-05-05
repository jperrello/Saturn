import os
import sys
import json
import socket
import logging
import argparse
import threading
import time

from contextlib import asynccontextmanager

from typing import Optional, List

import hmac

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Depends


import signal
from pathlib import Path

from dotenv import load_dotenv

from .config import load_service_config, ServiceConfig, list_service_configs, SERVICES_DIR
from .discovery import SaturnAdvertiser, get_lan_ip
from .servers import ChatMessage, ChatRequest, proxy_sse

SATURN_ENV_FILE = Path.home() / ".saturn" / ".env"
load_dotenv(SATURN_ENV_FILE)

logger = logging.getLogger("saturn.runner")

RUN_DIR = Path.home() / ".saturn" / "run"



def write_service_info(name: str, port: int, mdns_name: str) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    service_file = RUN_DIR / f"{name}.json"
    info = {
        "pid": os.getpid(),
        "port": port,
        "mdns_name": mdns_name,
    }
    service_file.write_text(json.dumps(info))
    return service_file


def read_service_info(name: str) -> Optional[dict]:
    service_file = RUN_DIR / f"{name}.json"
    if not service_file.exists():
        return None
    try:
        return json.loads(service_file.read_text())
    except (ValueError, OSError, json.JSONDecodeError):
        return None


def remove_service_info(name: str) -> None:
    service_file = RUN_DIR / f"{name}.json"
    if service_file.exists():
        service_file.unlink()
    pid_file = RUN_DIR / f"{name}.pid"
    if pid_file.exists():
        pid_file.unlink()


def is_service_running(name: str) -> bool:
    from .discovery import discover
    services = discover(timeout=3.0, settle_time=0.5)
    return any(s.name.startswith(name) for s in services)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


class CredentialManager:
    def __init__(self, provider, api_key, rotation_interval=400,
                 expiration_interval=600, max_budget_usd=None):
        self.provider = provider
        self.api_key = api_key
        self.endpoint = provider.endpoint
        self.api_base = provider.api_base
        self.rotation_interval = rotation_interval
        self.expiration_interval = expiration_interval
        self.max_budget_usd = max_budget_usd
        self._lock = threading.Lock()
        self._credential: Optional[str] = None
        self._handles: list = []
        self._last_rotation: Optional[float] = None
        self._sleep_invalidated: bool = False

    def create(self) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            payload = self.provider.payload(self.expiration_interval, max_budget_usd=self.max_budget_usd)
        except TypeError:
            payload = self.provider.payload(self.expiration_interval)
        response = requests.post(self.endpoint, headers=headers, json=payload)
        response.raise_for_status()
        credential, handle = self.provider.parse(response.json())
        with self._lock:
            self._credential = credential
            if handle is not None:
                self._handles.append(handle)
            self._last_rotation = time.time()
        return credential

    def current(self) -> Optional[str]:
        with self._lock:
            return self._credential

    def stale(self) -> bool:
        with self._lock:
            if self._last_rotation is None:
                return True
            return time.time() - self._last_rotation >= self.rotation_interval

    def invalidate(self) -> None:
        with self._lock:
            self._sleep_invalidated = True

    def needs_remint(self) -> bool:
        with self._lock:
            return self._sleep_invalidated

    def mark_fresh(self) -> None:
        with self._lock:
            self._sleep_invalidated = False

    def cleanup(self, final=False) -> None:
        with self._lock:
            if final:
                handles = list(self._handles)
                self._handles.clear()
            else:
                if len(self._handles) > 1:
                    handles = self._handles[:-1]
                    self._handles = self._handles[-1:]
                else:
                    handles = []
        for h in handles:
            self.provider.revoke(self.api_key, self.endpoint, h)


class BeaconAdvertiser(SaturnAdvertiser):
    def __init__(self, name: str, port: int, priority: int, api_base: str,
                 credential_manager: CredentialManager):
        super().__init__(
            name=name,
            port=port,
            priority=priority,
            deployment='cloud',
            api_type='openai',
            api_base=api_base,
        )
        self.credential_manager = credential_manager

    def _properties(self) -> dict:
        credential = self.credential_manager.current()
        if not credential:
            credential = self.credential_manager.create()
        if len(credential) > 240:
            logger.warning(f"Credential length ({len(credential)}) exceeds safe mDNS limit (240)")
        return {
            'version': '1.0',
            'deployment': self.deployment,
            'api_type': self.api_type,
            'api_base': self.api_base,
            'priority': str(self.priority),
            'ephemeral_key': credential,
            'features': 'ephemeral_auth',
        }

    def register(self) -> bool:
        from saturn.mdns.backend import AdvertiseSpec
        from saturn.discovery import get_lan_ip
        try:
            if not self.api_base:
                self.api_base = f"http://{get_lan_ip()}:{self.port}/v1"
            ttl = min(self.credential_manager.expiration_interval, 4500)
            spec = AdvertiseSpec(
                name=self.name,
                port=self.port,
                txt=self._properties(),
                ttl=ttl,
            )
            self._backend.advertise(spec)
            logger.info(f"Registered {self.name} on {self.SERVICE_TYPE} at port {self.port} with priority {self.priority}")
            return True
        except Exception as e:
            logger.error(f"Failed to register beacon: {e}")
            return False

    def re_register(self) -> None:
        logger.info("Re-registering beacon with updated credential...")
        self.unregister()
        self.register()


def _beacon_on_sleep(beacon, credential_manager) -> None:
    try:
        beacon.unregister()
    except Exception as e:
        logger.warning(f"beacon.unregister on sleep failed: {e}")
    credential_manager.invalidate()


def _beacon_on_wake(beacon, credential_manager) -> None:
    credential_manager.create()
    credential_manager.mark_fresh()
    try:
        beacon.re_register()
    except Exception as e:
        logger.warning(f"beacon.re_register on wake failed: {e}")


def _rotation_tick(credential_manager, last_tick_monotonic: float, rotation_interval: float, now_monotonic: float) -> float:
    if now_monotonic - last_tick_monotonic > 2 * rotation_interval:
        credential_manager.create()
        credential_manager.mark_fresh()
    return now_monotonic


def _warn_no_sleep_handling() -> None:
    logger.warning(
        "saturn beacon: no sleep handling installed (SECURITY_AUDIT §16). "
        "Set beacon.keep_awake=true in the service config OR run saturn under "
        "caffeinate / systemd-inhibit to prevent unwitnessed sleep gaps."
    )


def _prompt_keep_awake(config_path) -> bool:
    from pathlib import Path as _Path
    try:
        import tomllib as _tomllib
    except ImportError:
        import tomli as _tomllib  # type: ignore
    p = _Path(config_path)
    cfg = _tomllib.loads(p.read_text())
    beacon = cfg.get("beacon") or {}
    if beacon.get("keep_awake_decided"):
        return bool(beacon.get("keep_awake", False))
    if not sys.stdin.isatty():
        return False
    answer = input("Keep this host awake while beacon runs? [Y/n] ").strip().lower()
    decision = answer in ("", "y", "yes")
    text = p.read_text()
    lines = text.splitlines()
    out = []
    in_beacon = False
    seen_keep_awake = False
    seen_keep_awake_decided = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[beacon]"):
            in_beacon = True
            out.append(line)
            continue
        if stripped.startswith("[") and in_beacon:
            if not seen_keep_awake:
                out.append(f"keep_awake = {'true' if decision else 'false'}")
            if not seen_keep_awake_decided:
                out.append("keep_awake_decided = true")
            in_beacon = False
        if in_beacon and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key == "keep_awake":
                seen_keep_awake = True
                line = f"keep_awake = {'true' if decision else 'false'}"
            elif key == "keep_awake_decided":
                seen_keep_awake_decided = True
                line = "keep_awake_decided = true"
        out.append(line)
    if in_beacon:
        if not seen_keep_awake:
            out.append(f"keep_awake = {'true' if decision else 'false'}")
        if not seen_keep_awake_decided:
            out.append("keep_awake_decided = true")
    p.write_text("\n".join(out) + "\n")
    return decision


def run_beacon(config: ServiceConfig, port: int = 8090) -> int:
    api_key = None
    if config.upstream.api_key_env:
        api_key = os.environ.get(config.upstream.api_key_env)
    if not api_key:
        logger.error(f"Environment variable {config.upstream.api_key_env} not set")
        return 1

    if not config.beacon.provider:
        logger.error("No beacon provider configured")
        return 1

    from saturn.providers import load
    try:
        provider = load(config.beacon.provider)
    except ValueError as e:
        logger.error(str(e))
        return 1

    credential_manager = CredentialManager(
        provider=provider,
        api_key=api_key,
        rotation_interval=config.beacon.rotation_interval,
        expiration_interval=config.beacon.expiration_interval,
        max_budget_usd=config.beacon.max_budget_usd,
    )

    if is_service_running(config.name):
        logger.error(f"Service '{config.name}' is already running")
        return 1

    mdns_name = f"{config.name}-Beacon"
    service_file = write_service_info(config.name, port, mdns_name)
    beacon = BeaconAdvertiser(
        name=config.name,
        port=port,
        priority=config.priority,
        api_base=credential_manager.api_base,
        credential_manager=credential_manager
    )

    shutdown_event = threading.Event()

    def shutdown_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print("=" * 55)
    print(f"  Saturn {config.beacon.provider.title()} Beacon")
    print("=" * 55)
    print()
    print("  This beacon broadcasts ephemeral credentials via mDNS.")
    print("  Clients discover the key and call the API directly.")
    print()
    print(f"  Provider: {config.beacon.provider.title()}")
    print(f"  Priority: {config.priority}")
    print(f"  Port (mDNS): {port}")
    print(f"  Rotation: every {config.beacon.rotation_interval}s")
    print()
    print("=" * 55)

    logger.info("Creating initial credential...")
    try:
        credential_manager.create()
    except Exception as e:
        logger.error(f"Failed to create credential: {e}")
        remove_service_info(config.name)
        return 1

    logger.info("Registering beacon on mDNS...")
    beacon.register()

    def rotation_loop():
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=10)
            if shutdown_event.is_set():
                break
            if credential_manager.stale():
                try:
                    logger.info("Rotating credential...")
                    credential_manager.create()
                    beacon.re_register()
                    credential_manager.cleanup()
                except Exception as e:
                    logger.error(f"Rotation failed: {e}")

    rotation_thread = threading.Thread(target=rotation_loop, daemon=True)
    rotation_thread.start()

    logger.info("Beacon is now discoverable! Press Ctrl+C to stop.")

    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1)
    except KeyboardInterrupt:
        pass

    logger.info("Shutting down beacon...")
    beacon.unregister()
    credential_manager.cleanup(final=True)
    remove_service_info(config.name)
    logger.info("Shutdown complete")
    return 0




class ServiceRunner:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.api_key: Optional[str] = None
        self.models_cache: List[str] = []
        self.app: Optional[FastAPI] = None
        self._advertiser = None

    def _get_api_key(self) -> Optional[str]:
        if self.config.upstream.api_key_env:
            return os.environ.get(self.config.upstream.api_key_env)
        return None

    def _fetch_models(self) -> List[str]:
        base_url = self.config.upstream.base_url.rstrip("/")
        models_url = f"{base_url}/models"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.get(models_url, headers=headers, timeout=30)
            if response.ok:
                data = response.json()
                if "data" in data:
                    return [m.get("id", "") for m in data["data"] if m.get("id")]
                elif "models" in data:
                    return [m.get("id", m.get("name", "")) for m in data["models"] if m.get("id") or m.get("name")]
            logger.warning(f"Failed to fetch models: {response.status_code}")
        except Exception as e:
            logger.warning(f"Error fetching models: {e}")

        return []

    def create_app(self) -> FastAPI:
        self.api_key = self._get_api_key()
        runner = self

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            logger.info(f"Starting {runner.config.name} service...")
            runner.models_cache = runner._fetch_models()
            if runner.models_cache:
                logger.info(f"Cached {len(runner.models_cache)} models")
            else:
                logger.warning("No models fetched at startup")
            if runner._advertiser is not None and runner.models_cache:
                runner._advertiser.models = runner.models_cache[:50]
                runner._advertiser.unregister()
                runner._advertiser.register()
            yield
            logger.info(f"Shutting down {runner.config.name} service...")

        app = FastAPI(lifespan=lifespan, title=f"Saturn - {self.config.name}")

        token_env = getattr(runner.config, "runner_token_env", None) or "SATURN_RUNNER_TOKEN"

        def auth(authorization: Optional[str] = Header(default=None)):
            expected = os.environ.get(token_env, "")
            unauthorized = HTTPException(
                status_code=401,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )
            if not expected:
                raise unauthorized
            if not authorization or not authorization.lower().startswith("bearer "):
                raise unauthorized
            presented = authorization.split(" ", 1)[1].strip()
            if not hmac.compare_digest(presented, expected):
                raise unauthorized
            return True

        @app.get("/v1/health")
        async def health(_=Depends(auth)):
            return {
                "status": "ok",
                "service": runner.config.name,
                "deployment": runner.config.deployment,
                "api_type": runner.config.api_type,
                "models_cached": len(runner.models_cache),
                "saturn": True,
            }

        @app.get("/v1/models")
        async def get_models(_=Depends(auth)):
            if not runner.models_cache:
                runner.models_cache = runner._fetch_models()

            if not runner.models_cache:
                raise HTTPException(status_code=503, detail="No models available")

            return {
                "object": "list",
                "data": [{"id": m, "object": "model", "owned_by": runner.config.name} for m in runner.models_cache],
            }

        @app.post("/v1/chat/completions")
        async def chat_completions(request: ChatRequest, _=Depends(auth)):
            base_url = runner.config.upstream.base_url.rstrip("/")
            completions_url = f"{base_url}/chat/completions"

            headers = {"Content-Type": "application/json"}
            if runner.api_key:
                headers["Authorization"] = f"Bearer {runner.api_key}"

            payload = {
                "model": request.model,
                "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            }
            if request.stream:
                payload["stream"] = True
            if request.temperature is not None:
                payload["temperature"] = request.temperature
            if request.max_tokens is not None:
                payload["max_tokens"] = request.max_tokens
            if request.tools is not None:
                payload["tools"] = request.tools
            if request.tool_choice is not None:
                payload["tool_choice"] = request.tool_choice

            try:
                response = requests.post(
                    completions_url,
                    headers=headers,
                    json=payload,
                    timeout=120,
                    stream=request.stream,
                )

                if not response.ok:
                    logger.error(f"Upstream error: {response.text}")
                    raise HTTPException(status_code=response.status_code, detail=f"Upstream error: {response.text}")

                if request.stream:
                    return proxy_sse(response)
                else:
                    return response.json()

            except requests.Timeout:
                raise HTTPException(status_code=504, detail="Upstream request timed out")
            except requests.RequestException as e:
                raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

        self.app = app
        return app


def _wrap_with_auth(inner_app, token_env: str = "SATURN_RUNNER_TOKEN"):
    async def asgi(scope, receive, send):
        if scope.get("type") == "http" and scope.get("path", "").startswith("/v1/"):
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode("latin-1")
            expected = os.environ.get(token_env, "")
            ok = (
                bool(expected)
                and auth.lower().startswith("bearer ")
                and hmac.compare_digest(auth.split(" ", 1)[1].strip(), expected)
            )
            if not ok:
                from starlette.responses import JSONResponse
                resp = JSONResponse(
                    {"detail": "Unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await resp(scope, receive, send)
                return
        await inner_app(scope, receive, send)
    return asgi


def build_app(config: ServiceConfig):
    if config.server.module:
        import importlib
        mod = importlib.import_module(config.server.module)
        return _wrap_with_auth(mod.app)
    runner = ServiceRunner(config)
    app = runner.create_app()
    app.state.runner = runner
    return app


def find_available_port(host: str, start_port: int = 8080) -> int:
    port = start_port
    while port < 65535:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            port += 1
    raise RuntimeError("No available port found")


def run_service(config: ServiceConfig, host: str = "127.0.0.1", port: Optional[int] = None) -> int:
    import atexit

    if config.beacon.enabled:
        beacon_port = port if port else (config.server.port if config.server.port > 0 else 8090)
        return run_beacon(config, port=beacon_port)

    if is_service_running(config.name):
        logger.error(f"Service '{config.name}' is already running")
        return 1

    errors = config.validate()
    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        return 1

    start_port = port if port else (config.server.port if config.server.port > 0 else 8080)
    actual_port = find_available_port(host, start_port)

    if port and actual_port != port:
        logger.info(f"Port {port} in use, using {actual_port}")

    app = build_app(config)
    svc_runner = getattr(getattr(app, "state", None), "runner", None)

    mdns_name = f"{config.name}-{actual_port}"
    advertiser = SaturnAdvertiser(
        name=mdns_name,
        port=actual_port,
        deployment=config.deployment,
        api_type=config.api_type,
        priority=config.priority,
        models=[],
        capabilities=["chat"],
    )

    if svc_runner is not None:
        svc_runner._advertiser = advertiser

    service_file = write_service_info(config.name, actual_port, mdns_name)
    logger.info(f"Starting {config.name} on {host}:{actual_port} with priority {config.priority}")
    logger.info(f"Service file: {service_file}")
    advertiser.register()

    def cleanup():
        logger.info("Shutting down...")
        advertiser.unregister()
        remove_service_info(config.name)

    atexit.register(cleanup)

    try:
        uvicorn.run(app, host=host, port=actual_port)
    finally:
        atexit.unregister(cleanup)
        cleanup()

    return 0




def _pid_alive(pid: int) -> bool:
    try:
        if sys.platform == "win32":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        os.kill(pid, 0)
        return True
    except OSError:
        return False



def stop_service(name: str) -> int:
    info = read_service_info(name)
    if not info or "pid" not in info:
        print(f"Service '{name}' is not running (no service info)")
        return 1

    pid = info["pid"]
    if not _pid_alive(pid):
        remove_service_info(name)
        print(f"Service '{name}' is not running (stale service info removed)")
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to {name} (PID {pid})")

        for _ in range(30):
            time.sleep(0.1)
            if not _pid_alive(pid):
                break

        remove_service_info(name)
        return 0
    except OSError as e:
        print(f"Failed to stop {name}: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Saturn service from config")
    parser.add_argument("name", nargs="?", help="Service name (from ~/.saturn/services/)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (loopback by default; set 0.0.0.0 to expose on LAN)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to")
    parser.add_argument("--list", "-l", action="store_true", help="List available services")
    args = parser.parse_args()

    if args.list:
        configs = list_service_configs()
        if not configs:
            print("No services configured.")
            print(f"Create one with: saturn config new")
            return 0

        print("Available services:")
        for name, cfg, is_builtin in configs:
            source = " (built-in)" if is_builtin else ""
            beacon = " [beacon]" if cfg.beacon.enabled else ""
            print(f"  {name}: {cfg.api_type} @ {cfg.upstream.base_url}{beacon}{source}")
        return 0

    if not args.name:
        parser.print_help()
        return 1

    config = load_service_config(args.name)
    if not config:
        print(f"Service '{args.name}' not found in {SERVICES_DIR}", file=sys.stderr)
        print(f"Create it with: saturn config new")
        return 1

    return run_service(config, host=args.host, port=args.port)


if __name__ == "__main__":
    sys.exit(main())
