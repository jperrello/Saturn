import os
import sys
import json
import socket
import logging
import argparse
import threading
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from zeroconf import Zeroconf, ServiceInfo

import signal
from pathlib import Path

from dotenv import load_dotenv

from .config import load_service_config, ServiceConfig, list_service_configs, SERVICES_DIR
from .discovery import SaturnAdvertiser, get_lan_ip

SATURN_ENV_FILE = Path.home() / ".saturn" / ".env"
load_dotenv(SATURN_ENV_FILE)

logger = logging.getLogger("saturn.runner")

RUN_DIR = Path.home() / ".saturn" / "run"


def get_service_file(name: str) -> Path:
    return RUN_DIR / f"{name}.json"


def get_pid_file(name: str) -> Path:
    return RUN_DIR / f"{name}.pid"


def write_service_info(name: str, port: int, mdns_name: str) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    service_file = get_service_file(name)
    info = {
        "pid": os.getpid(),
        "port": port,
        "mdns_name": mdns_name,
    }
    service_file.write_text(json.dumps(info))
    return service_file


def read_service_info(name: str) -> Optional[dict]:
    service_file = get_service_file(name)
    if not service_file.exists():
        return None
    try:
        return json.loads(service_file.read_text())
    except (ValueError, OSError, json.JSONDecodeError):
        return None


def write_pid_file(name: str) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    pid_file = get_pid_file(name)
    pid_file.write_text(str(os.getpid()))
    return pid_file


def read_pid_file(name: str) -> Optional[int]:
    info = read_service_info(name)
    if info and "pid" in info:
        return info["pid"]
    pid_file = get_pid_file(name)
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def remove_pid_file(name: str) -> None:
    service_file = get_service_file(name)
    if service_file.exists():
        service_file.unlink()
    pid_file = get_pid_file(name)
    if pid_file.exists():
        pid_file.unlink()


def is_service_running(name: str) -> bool:
    pid = read_pid_file(name)
    if pid is None:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            remove_pid_file(name)
            return False
        else:
            os.kill(pid, 0)
            return True
    except OSError:
        remove_pid_file(name)
        return False


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


class CredentialManager(ABC):
    @abstractmethod
    def create_credential(self) -> str:
        pass

    @abstractmethod
    def get_current_credential(self) -> Optional[str]:
        pass

    @abstractmethod
    def needs_rotation(self) -> bool:
        pass

    @abstractmethod
    def cleanup(self) -> None:
        pass


class DeepInfraJWTManager(CredentialManager):
    def __init__(self, api_key: str, rotation_interval: int = 300, expiration_interval: int = 600,
                 spending_limit: float = 0, key_endpoint: str = "", api_base: str = ""):
        self.api_key = api_key
        self.rotation_interval = rotation_interval
        self.expiration_interval = expiration_interval
        self.spending_limit = spending_limit if spending_limit > 0 else None
        self.api_endpoint = key_endpoint or "https://api.deepinfra.com/v1/scoped-jwt"
        self.api_base = api_base or "https://api.deepinfra.com/v1/openai"
        self._lock = threading.Lock()
        self._current_token: Optional[str] = None
        self._last_rotation: Optional[float] = None

    def create_credential(self) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "api_key_name": "auto",
            "expires_delta": self.expiration_interval
        }
        if self.spending_limit is not None:
            payload["spending_limit"] = self.spending_limit
        response = requests.post(self.api_endpoint, headers=headers, json=payload)
        response.raise_for_status()
        token = response.json()["token"]
        with self._lock:
            self._current_token = token
            self._last_rotation = time.time()
        return token

    def get_current_credential(self) -> Optional[str]:
        with self._lock:
            return self._current_token

    def needs_rotation(self) -> bool:
        with self._lock:
            if self._last_rotation is None:
                return True
            return time.time() - self._last_rotation >= self.rotation_interval

    def cleanup(self) -> None:
        pass


class OpenRouterKeyManager(CredentialManager):
    def __init__(self, provisioning_key: str, rotation_interval: int = 300,
                 expiration_interval: int = 600, spending_limit: float = 0):
        self.provisioning_key = provisioning_key
        self.rotation_interval = rotation_interval
        self.expiration_interval = expiration_interval
        self.spending_limit = spending_limit if spending_limit > 0 else None
        self.keys_url = "https://openrouter.ai/api/v1/keys"
        self.api_base = "https://openrouter.ai/api/v1"
        self._lock = threading.Lock()
        self._current_key: Optional[str] = None
        self._current_hash: Optional[str] = None
        self._previous_hash: Optional[str] = None
        self._last_rotation: Optional[float] = None

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.provisioning_key}",
            "Content-Type": "application/json"
        }

    def create_credential(self) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.expiration_interval)
        expires_at_str = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            "name": f"saturn-beacon-{int(time.time())}",
            "expires_at": expires_at_str
        }
        if self.spending_limit is not None:
            payload["limit"] = self.spending_limit
        response = requests.post(self.keys_url, headers=self._get_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        key = data["key"]
        key_hash = data["data"]["hash"]
        with self._lock:
            if self._current_hash:
                self._previous_hash = self._current_hash
            self._current_key = key
            self._current_hash = key_hash
            self._last_rotation = time.time()
        return key

    def get_current_credential(self) -> Optional[str]:
        with self._lock:
            return self._current_key

    def needs_rotation(self) -> bool:
        with self._lock:
            if self._last_rotation is None:
                return True
            return time.time() - self._last_rotation >= self.rotation_interval

    def _delete_key(self, key_hash: str) -> bool:
        try:
            response = requests.delete(f"{self.keys_url}/{key_hash}", headers=self._get_headers())
            if response.status_code in (200, 404):
                logger.info(f"Deleted key: {key_hash[:8]}...")
                return True
            logger.warning(f"Failed to delete key {key_hash[:8]}...: {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Error deleting key: {e}")
            return False

    def cleanup(self) -> None:
        with self._lock:
            previous = self._previous_hash
            current = self._current_hash
            self._previous_hash = None
        if previous:
            self._delete_key(previous)
        if current:
            self._delete_key(current)


class BeaconAnnouncer:
    SERVICE_TYPE = "_saturn._tcp.local."

    def __init__(self, name: str, port: int, priority: int, api_base: str,
                 credential_manager: CredentialManager):
        self.name = name
        self.port = port
        self.priority = priority
        self.api_base = api_base
        self.credential_manager = credential_manager
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None
        self._is_registered = False

    def register(self) -> None:
        if self._is_registered:
            logger.warning("Service already registered")
            return
        credential = self.credential_manager.get_current_credential()
        if not credential:
            credential = self.credential_manager.create_credential()
        if len(credential) > 240:
            logger.warning(f"Credential length ({len(credential)}) exceeds safe mDNS limit (240)")
        host = socket.gethostname()
        host_ip = get_lan_ip()
        service_name = f"{self.name}-Beacon.{self.SERVICE_TYPE}"
        self._zeroconf = Zeroconf()
        self._service_info = ServiceInfo(
            type_=self.SERVICE_TYPE,
            name=service_name,
            port=self.port,
            addresses=[socket.inet_aton(host_ip)],
            server=f"{host}.local.",
            properties={
                'version': '1.0',
                'deployment': 'cloud',
                'api_type': 'openai',
                'api_base': self.api_base,
                'priority': str(self.priority),
                'ephemeral_key': credential,
                'features': 'ephemeral_auth'
            }
        )
        self._zeroconf.register_service(self._service_info)
        self._is_registered = True
        logger.info(f"Beacon registered: {service_name} on port {self.port}")

    def unregister(self) -> None:
        if not self._is_registered:
            return
        if self._zeroconf and self._service_info:
            logger.info("Unregistering beacon...")
            self._zeroconf.unregister_service(self._service_info)
            self._zeroconf.close()
        self._zeroconf = None
        self._service_info = None
        self._is_registered = False

    def re_register(self) -> None:
        logger.info("Re-registering beacon with updated credential...")
        self.unregister()
        self.register()


def run_beacon(config: ServiceConfig, port: int = 8090) -> int:
    api_key = None
    if config.upstream.api_key_env:
        api_key = os.environ.get(config.upstream.api_key_env)
    if not api_key:
        logger.error(f"Environment variable {config.upstream.api_key_env} not set")
        return 1

    key_endpoint = config.beacon.key_endpoint or ""
    if "deepinfra" in key_endpoint.lower() or "deepinfra" in config.upstream.base_url.lower():
        credential_manager = DeepInfraJWTManager(
            api_key=api_key,
            rotation_interval=config.beacon.rotation_interval,
            expiration_interval=config.beacon.expiration_interval,
            spending_limit=config.beacon.spending_limit,
            key_endpoint=config.beacon.key_endpoint or "",
            api_base=config.upstream.base_url
        )
        api_base = config.upstream.base_url or "https://api.deepinfra.com/v1/openai"
        provider_name = "DeepInfra"
    elif "openrouter" in key_endpoint.lower() or "openrouter" in config.upstream.base_url.lower():
        credential_manager = OpenRouterKeyManager(
            provisioning_key=api_key,
            rotation_interval=config.beacon.rotation_interval,
            expiration_interval=config.beacon.expiration_interval,
            spending_limit=config.beacon.spending_limit
        )
        api_base = "https://openrouter.ai/api/v1"
        provider_name = "OpenRouter"
    else:
        logger.error("Unknown beacon provider. key_endpoint must contain 'deepinfra' or 'openrouter'")
        return 1

    if is_service_running(config.name):
        logger.error(f"Service '{config.name}' is already running")
        return 1

    mdns_name = f"{config.name}-Beacon"
    service_file = write_service_info(config.name, port, mdns_name)
    beacon = BeaconAnnouncer(
        name=config.name,
        port=port,
        priority=config.priority,
        api_base=api_base,
        credential_manager=credential_manager
    )

    shutdown_event = threading.Event()

    def shutdown_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print("=" * 55)
    print(f"  Saturn {provider_name} Beacon")
    print("=" * 55)
    print()
    print("  This beacon broadcasts ephemeral credentials via mDNS.")
    print("  Clients discover the key and call the API directly.")
    print()
    print(f"  Provider: {provider_name}")
    print(f"  Priority: {config.priority}")
    print(f"  Port (mDNS): {port}")
    print(f"  Rotation: every {config.beacon.rotation_interval}s")
    if config.beacon.spending_limit > 0:
        print(f"  Spending limit: ${config.beacon.spending_limit}")
    print()
    print("=" * 55)

    logger.info("Creating initial credential...")
    try:
        credential_manager.create_credential()
    except Exception as e:
        logger.error(f"Failed to create credential: {e}")
        remove_pid_file(config.name)
        return 1

    logger.info("Registering beacon on mDNS...")
    beacon.register()

    def rotation_loop():
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=10)
            if shutdown_event.is_set():
                break
            if credential_manager.needs_rotation():
                try:
                    logger.info("Rotating credential...")
                    credential_manager.create_credential()
                    beacon.re_register()
                    if hasattr(credential_manager, '_previous_hash') and credential_manager._previous_hash:
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
    credential_manager.cleanup()
    remove_pid_file(config.name)
    logger.info("Shutdown complete")
    return 0


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


class ServiceRunner:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.api_key: Optional[str] = None
        self.models_cache: List[str] = []
        self.app: Optional[FastAPI] = None

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
            yield
            logger.info(f"Shutting down {runner.config.name} service...")

        app = FastAPI(lifespan=lifespan, title=f"Saturn - {self.config.name}")

        @app.get("/v1/health")
        async def health():
            return {
                "status": "ok",
                "service": runner.config.name,
                "deployment": runner.config.deployment,
                "api_type": runner.config.api_type,
                "models_cached": len(runner.models_cache),
                "saturn": True,
            }

        @app.get("/v1/models")
        async def get_models():
            if not runner.models_cache:
                runner.models_cache = runner._fetch_models()

            if not runner.models_cache:
                raise HTTPException(status_code=503, detail="No models available")

            return {
                "object": "list",
                "data": [{"id": m, "object": "model", "owned_by": runner.config.name} for m in runner.models_cache],
            }

        @app.post("/v1/chat/completions")
        async def chat_completions(request: ChatRequest):
            base_url = runner.config.upstream.base_url.rstrip("/")
            completions_url = f"{base_url}/chat/completions"

            headers = {"Content-Type": "application/json"}
            if runner.api_key:
                headers["Authorization"] = f"Bearer {runner.api_key}"

            payload = {
                "model": request.model,
                "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            }
            if request.max_tokens is not None:
                payload["max_tokens"] = request.max_tokens
            if request.temperature is not None:
                payload["temperature"] = request.temperature
            if request.stream:
                payload["stream"] = True

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
                    def generate():
                        try:
                            for line in response.iter_lines():
                                if line:
                                    decoded = line.decode("utf-8")
                                    if decoded.startswith("data: "):
                                        data = decoded[6:]
                                        if data == "[DONE]":
                                            yield b"data: [DONE]\n\n"
                                            break
                                        try:
                                            chunk = json.loads(data)
                                            yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                                        except json.JSONDecodeError:
                                            continue
                        finally:
                            response.close()

                    return StreamingResponse(
                        generate(),
                        media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                    )
                else:
                    return response.json()

            except requests.Timeout:
                raise HTTPException(status_code=504, detail="Upstream request timed out")
            except requests.RequestException as e:
                raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

        self.app = app
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


def run_service(config: ServiceConfig, host: str = "0.0.0.0", port: Optional[int] = None) -> int:
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

    models_for_mdns = []

    if config.server.module:
        import importlib
        mod = importlib.import_module(config.server.module)
        app = mod.app
    else:
        runner = ServiceRunner(config)
        app = runner.create_app()
        models_for_mdns = runner.models_cache[:50]

    mdns_name = f"{config.name}-{actual_port}"
    advertiser = SaturnAdvertiser(
        name=mdns_name,
        port=actual_port,
        deployment=config.deployment,
        api_type=config.api_type,
        priority=config.priority,
        models=models_for_mdns,
        capabilities=["chat"],
    )

    service_file = write_service_info(config.name, actual_port, mdns_name)
    logger.info(f"Starting {config.name} on {host}:{actual_port} with priority {config.priority}")
    logger.info(f"Service file: {service_file}")
    advertiser.register()

    def cleanup():
        logger.info("Shutting down...")
        advertiser.unregister()
        remove_pid_file(config.name)

    atexit.register(cleanup)

    try:
        uvicorn.run(app, host=host, port=actual_port)
    finally:
        atexit.unregister(cleanup)
        cleanup()

    return 0



def unregister_mdns_service(mdns_name: str, port: int) -> bool:
    SERVICE_TYPE = "_saturn._tcp.local."
    try:
        host = socket.gethostname()
        host_ip = get_lan_ip()

        zc = Zeroconf()
        info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=f"{mdns_name}.{SERVICE_TYPE}",
            port=port,
            addresses=[socket.inet_aton(host_ip)],
            server=f"{host}.local.",
            properties={},
        )
        zc.unregister_service(info)
        zc.close()
        logger.info(f"Unregistered {mdns_name} from mDNS")
        return True
    except Exception as e:
        logger.warning(f"Failed to unregister mDNS service: {e}")
        return False

def stop_service(name: str) -> int:
    service_info = read_service_info(name)
    pid = read_pid_file(name)
    if pid is None:
        print(f"Service '{name}' is not running (no PID file)")
        return 1

    if not is_service_running(name):
        print(f"Service '{name}' is not running (stale PID file removed)")
        return 1

    try:
        if sys.platform == "win32":
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to {name} (PID {pid})")

        for _ in range(30):
            time.sleep(0.1)
            if not is_service_running(name):
                break

        if service_info and "mdns_name" in service_info and "port" in service_info:
            unregister_mdns_service(service_info["mdns_name"], service_info["port"])

        remove_pid_file(name)
        return 0
    except OSError as e:
        print(f"Failed to stop {name}: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Saturn service from config")
    parser.add_argument("name", nargs="?", help="Service name (from ~/.saturn/services/)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to")
    parser.add_argument("--list", "-l", action="store_true", help="List available services")
    args = parser.parse_args()

    if args.list:
        configs = list_service_configs()
        if not configs:
            print("No services configured.")
            print(f"Create one with: saturn config edit <name>")
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
        print(f"Create it with: saturn config edit {args.name}")
        return 1

    return run_service(config, host=args.host, port=args.port)


if __name__ == "__main__":
    sys.exit(main())
