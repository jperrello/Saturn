import argparse
import socket
import json
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import os
import subprocess
import uvicorn
import requests
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import threading
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rings.saturn_rings import RingsAdvertiser

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

if not OPENROUTER_API_KEY or not OPENROUTER_BASE_URL:
    raise ValueError(
        "Missing environment variables. "
        "Please set OPENROUTER_API_KEY and OPENROUTER_BASE_URL in your .env file"
    )

class ModelCache:
    def __init__(self):
        self.models: List[Dict[str, Any]] = []
        self.last_updated: Optional[datetime] = None
        self.lock = threading.Lock()

    def update(self, models: List[Dict[str, Any]]):
        with self.lock:
            self.models = models
            self.last_updated = datetime.now()

    def get(self) -> List[Dict[str, Any]]:
        with self.lock:
            return self.models.copy()

    def needs_refresh(self, max_age_hours: int = 1) -> bool:
        with self.lock:
            if not self.last_updated:
                return True
            return datetime.now() - self.last_updated > timedelta(hours=max_age_hours)

model_cache = ModelCache()

def fetch_openrouter_models() -> List[Dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }

    try:
        print("Fetching models from OpenRouter API...")
        response = requests.get(OPENROUTER_MODELS_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "data" in data:
            models = data["data"]
        else:
            models = data

        formatted_models = []

        auto_model = {
            "id": "openrouter/auto",
            "object": "model",
            "owned_by": "openrouter",
            "context_length": None,
            "pricing": None,
            "modality": "multimodal",
            "description": "Intelligent routing to best model via NotDiamond"
        }
        formatted_models.append(auto_model)

        for model in models:
            if isinstance(model, dict) and "id" in model:
                formatted_models.append({
                    "id": model["id"],
                    "object": "model",
                    "owned_by": model.get("owned_by", "openrouter"),
                    "context_length": model.get("context_length"),
                    "pricing": model.get("pricing"),
                    "modality": model.get("modality", "text"),
                })

        print(f"Successfully fetched {len(formatted_models)} models from OpenRouter")
        return formatted_models
    except requests.RequestException as e:
        print(f"Failed to fetch OpenRouter models: {e}")
        return []

def get_model_names() -> List[str]:
    models = fetch_openrouter_models()
    return [m["id"] for m in models[:20]]

async def refresh_models_if_needed():
    if model_cache.needs_refresh():
        print("Model cache is stale, refreshing...")
        models = fetch_openrouter_models()
        if models:
            model_cache.update(models)
            print(f"Successfully refreshed cache with {len(models)} models")
        else:
            print("Failed to refresh models, keeping existing cache")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("Starting up Saturn Rings OpenRouter server...")
    print("=" * 50)
    models = fetch_openrouter_models()
    if models:
        model_cache.update(models)
        print(f"Cached {len(models)} models from OpenRouter")
    else:
        print("WARNING: Failed to fetch models at startup.")

    yield

    print("Shutting down OpenRouter server...")

app = FastAPI(
    title="Saturn Rings OpenRouter",
    description="OpenRouter proxy with dual mDNS registration (_saturn._tcp + _rings._tcp)",
    summary="OpenRouter proxy with MCP-compatible discovery",
    version="2.0",
    contact={
        "name": "Joey Perrello",
        "url": "https://jperrello.netlify.app/",
        "email": "jperrell@ucsc.edu",
    },
    lifespan=lifespan
)

class UserAIRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    max_tokens: Optional[int] = None
    stream: bool = False

@app.get("/v1/health", description="Get's the health of server")
async def health() -> dict:
    return {
        "status": "ok",
        "provider": "OpenRouter",
        "models_cached": len(model_cache.get()),
        "features": ["multimodal", "auto-routing", "full-catalog"],
        "rings": True
    }

@app.get("/v1/models", description="Get's all available models from OpenRouter")
async def get_models() -> dict:
    await refresh_models_if_needed()

    cached_models = model_cache.get()

    if not cached_models:
        raise HTTPException(
            status_code=503,
            detail="No models available. Failed to fetch from OpenRouter API."
        )

    return {"models": cached_models}

@app.post("/v1/chat/completions", description="Get's a chat completion from the AI model")
async def chat_completions(request: UserAIRequest):
    print(f"Received request for model: {request.model}")
    print(f"Messages count: {len(request.messages)}, stream: {request.stream}")

    openrouter_request = {
        "model": request.model,
        "messages": request.messages
    }
    if request.max_tokens is not None:
        openrouter_request["max_tokens"] = request.max_tokens
    if request.stream:
        openrouter_request["stream"] = True

    print(f"Forwarding to OpenRouter with model: {request.model}, stream: {request.stream}")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            OPENROUTER_BASE_URL,
            headers=headers,
            json=openrouter_request,
            timeout=120,
            stream=request.stream
        )

        print(f"OpenRouter response status: {response.status_code}")

        if not response.ok:
            print(f"OpenRouter error response: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"OpenRouter API error: {response.text}"
            )

        if request.stream:
            print(f"Returning streaming response")

            def generate():
                try:
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith('data: '):
                                data_content = decoded_line[6:]

                                if data_content == '[DONE]':
                                    yield f"data: [DONE]\n\n".encode('utf-8')
                                    break

                                try:
                                    chunk_data = json.loads(data_content)
                                    yield f"data: {json.dumps(chunk_data)}\n\n".encode('utf-8')
                                except json.JSONDecodeError:
                                    continue
                finally:
                    response.close()

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
            try:
                result = response.json()
                print(f"OpenRouter response parsed successfully")
                return result
            except requests.exceptions.JSONDecodeError:
                raise HTTPException(
                    status_code=502,
                    detail=f"OpenRouter returned non-JSON response. Status: {response.status_code}"
                )

    except requests.Timeout:
        print(f"OpenRouter request timed out")
        raise HTTPException(status_code=504, detail="OpenRouter request timed out")
    except requests.RequestException as e:
        print(f"OpenRouter connection error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"OpenRouter connection error: {str(e)}")


def find_available_priority(desired_priority: int, service_type: str) -> int:
    priorities = set()

    try:
        browse_proc = subprocess.Popen(
            ['dns-sd', '-B', service_type, 'local'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        time.sleep(2.0)
        browse_proc.terminate()

        stdout, _ = browse_proc.communicate(timeout=1)

        for line in stdout.split('\n'):
            if service_type in line:
                try:
                    service_name = line.split()[6] if len(line.split()) > 6 else None
                    if service_name:
                        lookup_proc = subprocess.run(
                            ['dns-sd', '-L', service_name, service_type],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            timeout=2
                        )
                        for lookup_line in lookup_proc.stdout.split('\n'):
                            if 'priority=' in lookup_line:
                                parts = lookup_line.split('priority=')
                                if len(parts) > 1:
                                    priority_str = parts[1].split()[0]
                                    priorities.add(int(priority_str))
                except (IndexError, ValueError, subprocess.TimeoutExpired):
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("dns-sd not available or timed out, using desired priority")
        return desired_priority

    current_priority = desired_priority
    while current_priority in priorities:
        print(f"Priority {current_priority} is already in use, trying {current_priority + 1}...")
        current_priority += 1

    if current_priority != desired_priority:
        print(f"Adjusted priority from {desired_priority} to {current_priority}")

    return current_priority

def register_saturn(port: int, priority: int, service_type: str) -> subprocess.Popen:
    actual_priority = find_available_priority(priority, service_type)

    service_name = "OpenRouter"

    try:
        registration_proc = subprocess.Popen(
            [
                'dns-sd', '-R',
                service_name, '_saturn._tcp', 'local',
                str(port),
                f'version=2.0',
                f'api=OpenRouter',
                f'features=multimodal,auto-routing,full-catalog',
                f'priority={actual_priority}'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print(f"{service_name} registered on _saturn._tcp with priority {actual_priority}")
        return registration_proc
    except FileNotFoundError:
        print("ERROR: dns-sd not found. Please install Bonjour services (Windows).")
        return None

def find_port_number(host: str, start_port=8080, max_attempts=20) -> int:
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                s.bind((host, port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available ports in range {start_port} - {start_port + max_attempts}")

def main():
    parser = argparse.ArgumentParser(description="Saturn Rings OpenRouter Server (Dual Registration)")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--priority", type=int, default=50)
    args = parser.parse_args()

    port = args.port if args.port else find_port_number(args.host)
    print(f"Starting OpenRouter proxy on {args.host}:{port} with priority {args.priority}...")
    print("Dual registration: _saturn._tcp + _rings._tcp")

    model_names = get_model_names()
    print(f"Sample models: {', '.join(model_names[:5])}...")

    saturn_proc = register_saturn(port, priority=args.priority, service_type="_saturn._tcp.local.")

    rings_advertiser = RingsAdvertiser(
        name="OpenRouter",
        port=port,
        models=model_names,
        context=128000,
        cost="paid",
        priority=args.priority,
        mcp="none",
        transport="http",
        auth="none",
        saturn="2.0",
    )
    rings_advertiser.register()

    try:
        uvicorn.run(app, host=args.host, port=port)
    finally:
        print("Shutting down...")
        if saturn_proc:
            saturn_proc.terminate()
            saturn_proc.wait(timeout=2)
        rings_advertiser.unregister()

if __name__ == "__main__":
    main()
