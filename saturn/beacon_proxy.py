import os
import sys
import time
import socket
import argparse
import logging
import threading
import json
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import requests
from dotenv import load_dotenv

from .discovery import SaturnAdvertiser

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
DEEPINFRA_MODELS_URL = "https://api.deepinfra.com/v1/openai/models"
DEEPINFRA_JWT_URL = "https://api.deepinfra.com/v1/scoped-jwt"


class JWTManager:
    # scoped jwts let guests use the service without seeing the real api key
    # tokens are short-lived and auto-rotate, so even if leaked the damage is limited
    def __init__(self, api_key: Optional[str] = None,
                 expires_delta: int = 600,
                 rotation_interval: int = 300):
        self.api_key = api_key or os.getenv('DEEPINFRA_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPINFRA_API_KEY not found in environment")

        self.expires_delta = expires_delta
        self.rotation_interval = rotation_interval

        self._lock = threading.Lock()
        self._current_token: Optional[str] = None
        self._last_rotation: Optional[float] = None

    def generate_token(self) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "api_key_name": "auto",
            "expires_delta": self.expires_delta
        }

        response = requests.post(DEEPINFRA_JWT_URL, headers=headers, json=payload, timeout=30)

        # 409 means the api key wasn't created with jwt permissions enabled
        # user needs to regenerate their key on deepinfra dashboard with jwt scope
        if response.status_code == 409:
            logger.error("DeepInfra 409 Conflict - this may indicate the API key doesn't support scoped JWTs")
            logger.error("Check https://deepinfra.com/dash/api_keys and ensure your key has JWT permissions")
            raise ValueError("DeepInfra API key conflict - check key permissions")

        response.raise_for_status()

        token = response.json()["token"]

        with self._lock:
            self._current_token = token
            self._last_rotation = time.time()

        logger.info(f"Generated new JWT (expires in {self.expires_delta}s)")
        return token

    def get_current_token(self) -> Optional[str]:
        with self._lock:
            return self._current_token

    def needs_rotation(self) -> bool:
        with self._lock:
            if self._last_rotation is None:
                return True
            return time.time() - self._last_rotation >= self.rotation_interval


class BeaconProxy:
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
        self.api_key = jwt_manager.api_key
        self._models_cache: List[Dict[str, Any]] = []
        self._models_cached_at: Optional[float] = None

    def get_auth_header(self) -> Dict[str, str]:
        token = self.jwt_manager.get_current_token()
        if not token:
            token = self.jwt_manager.generate_token()
        return {"Authorization": f"Bearer {token}"}

    def fetch_models(self) -> List[Dict[str, Any]]:
        if self._models_cached_at and time.time() - self._models_cached_at < 3600:
            return self._models_cache

        try:
            response = requests.get(
                DEEPINFRA_MODELS_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            self._models_cache = data.get("data", [])
            self._models_cached_at = time.time()
            logger.info(f"Cached {len(self._models_cache)} models from DeepInfra")
            return self._models_cache
        except Exception as e:
            logger.error(f"Failed to fetch models: {e}")
            return self._models_cache

    def proxy_chat_completion(self, request_data: dict, stream: bool = False):
        headers = {
            **self.get_auth_header(),
            "Content-Type": "application/json"
        }

        response = requests.post(
            DEEPINFRA_API_URL,
            headers=headers,
            json=request_data,
            timeout=120,
            stream=stream
        )

        if not response.ok:
            logger.error(f"DeepInfra error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"DeepInfra API error: {response.text}"
            )

        return response


_jwt_manager: Optional[JWTManager] = None
_beacon_proxy: Optional[BeaconProxy] = None
_advertiser: Optional[SaturnAdvertiser] = None


def rotation_loop(jwt_manager: JWTManager):
    logger.info("JWT rotation loop started (rotating every 5 minutes)")
    while True:
        try:
            if jwt_manager.needs_rotation():
                try:
                    jwt_manager.generate_token()
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        logger.warning("Rate limited by DeepInfra, will retry next cycle")
                    else:
                        logger.error(f"HTTP error during rotation: {e}")
                except Exception as e:
                    logger.error(f"Error during rotation: {e}")
            time.sleep(60)
        except Exception as e:
            logger.error(f"Error in rotation loop: {e}")
            time.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _jwt_manager, _beacon_proxy

    logger.info("Initializing Beacon Proxy...")

    _jwt_manager = JWTManager()
    _jwt_manager.generate_token()
    _beacon_proxy = BeaconProxy(_jwt_manager)

    rotation_thread = threading.Thread(
        target=rotation_loop,
        args=(_jwt_manager,),
        daemon=True,
        name="JWTRotationThread"
    )
    rotation_thread.start()

    _beacon_proxy.fetch_models()

    yield

    logger.info("Shutting down Beacon Proxy...")


app = FastAPI(
    title="Saturn Beacon",
    description="Proxy beacon with automatic JWT rotation for DeepInfra",
    version="2.0",
    lifespan=lifespan
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    stream: bool = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None


@app.get("/v1/health")
async def health():
    token = _jwt_manager.get_current_token() if _jwt_manager else None
    return {
        "status": "ok" if token else "no_token",
        "provider": "DeepInfra (via Saturn Beacon)",
        "jwt_active": token is not None,
        "beacon": True
    }


@app.get("/v1/models")
async def get_models():
    if not _beacon_proxy:
        raise HTTPException(status_code=503, detail="Beacon not initialized")

    models = _beacon_proxy.fetch_models()

    formatted = [
        {
            "id": m.get("id", m.get("model")),
            "object": "model",
            "owned_by": m.get("owned_by", "deepinfra")
        }
        for m in models
    ]

    return {"models": formatted}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest, raw_request: Request):
    if not _beacon_proxy:
        raise HTTPException(status_code=503, detail="Beacon not initialized")

    logger.info(f"Proxying request for model: {request.model}, stream: {request.stream}")

    request_data = {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "stream": request.stream
    }

    if request.max_tokens:
        request_data["max_tokens"] = request.max_tokens
    if request.temperature is not None:
        request_data["temperature"] = request.temperature
    if request.top_p is not None:
        request_data["top_p"] = request.top_p

    response = _beacon_proxy.proxy_chat_completion(request_data, stream=request.stream)

    if request.stream:
        async def generate():
            try:
                for line in response.iter_lines():
                    if await raw_request.is_disconnected():
                        break
                    if line:
                        decoded = line.decode('utf-8') if isinstance(line, bytes) else line
                        if decoded.strip() == 'data: [DONE]':
                            yield b'data: [DONE]\n\n'
                            break
                        yield line + b'\n\n'
            finally:
                response.close()

        # x-accel-buffering: no is critical for nginx proxies, otherwise sse chunks get batched
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        return JSONResponse(content=response.json())


def find_port(host: str, start_port: int = 8080, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                s.bind((host, port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available ports in range {start_port}-{start_port + max_attempts}")


def main():
    global _advertiser

    parser = argparse.ArgumentParser(
        prog='saturn-beacon-proxy',
        description='Saturn Beacon Proxy: HTTP proxy server with automatic JWT rotation'
    )
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=None,
                        help='Port to bind to (default: auto-detect)')
    parser.add_argument('--priority', type=int, default=10,
                        help='mDNS priority (default: 10, lower = preferred)')
    args = parser.parse_args()

    if not os.getenv('DEEPINFRA_API_KEY'):
        logger.error("DEEPINFRA_API_KEY environment variable not set")
        logger.error("Get your API key from https://deepinfra.com/dash/api_keys")
        sys.exit(1)

    port = args.port if args.port else find_port(args.host)

    print("=" * 55)
    print("  Saturn Beacon Proxy")
    print("=" * 55)
    print()
    print("  This is the HTTP proxy version. All client traffic")
    print("  passes through this server to DeepInfra.")
    print()
    print(f"  Proxy running at http://{args.host}:{port}")
    print()
    print("  Guests configure their tools with:")
    print(f"    Base URL:  http://<your-ip>:{port}/v1")
    print(f"    API Key:   saturn  (or any string)")
    print()
    print("  JWT rotation happens automatically every 5 minutes.")
    print("=" * 55)

    _advertiser = SaturnAdvertiser(
        name="Beacon",
        port=port,
        models=["meta-llama/Llama-3.3-70B-Instruct", "deepseek-ai/DeepSeek-V3"],
        capabilities=["chat", "code"],
        context=128000,
        cost="paid",
        priority=args.priority,
        mcp="none",
    )
    _advertiser.register()

    try:
        uvicorn.run(app, host=args.host, port=port, log_level="info")
    finally:
        logger.info("Shutting down...")
        if _advertiser:
            _advertiser.unregister()


if __name__ == "__main__":
    main()
