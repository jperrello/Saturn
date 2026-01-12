"""
Saturn Fallback Server - Zeroconf Implementation

This server uses the Python zeroconf library for service registration and discovery.
This is an alternative implementation to demonstrate different approaches.

For a DNS-SD command-based implementation (using subprocess and dns-sd commands),
see servers/openrouter_server.py or servers/ollama_server.py.

Both approaches achieve the same goal - announcing Saturn services on the local network.
The zeroconf library provides a pure-Python solution, while dns-sd uses the native
system mDNS responder (available on macOS/Linux/Windows with Bonjour).
"""

import argparse
import random
import socket
import time
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser, ServiceListener
import uvicorn
from pydantic import BaseModel
from typing import Literal, Dict, Any
import threading

class CurrentChatContent(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class UserAIRequest(BaseModel):
    model: str
    messages: list[CurrentChatContent]
    max_tokens: int | None = None
    stream: bool = False

app = FastAPI(
    title="Saturn Totally Awesome and Effective Fallback Server",
    description="Saturn is a really cool protocol that allows you to connect to llm services through your local network. This is a fallback server that does nothing and doesn't use the technology to its fullest potential.",
    summary="Get LLMs anywhere you go, just not here! This is a fallback server.",
    version="1.0",
    contact={
        "name": "Joey Perrello",
        "url": "https://jperrello.netlify.app/",
        "email": "jperrell@ucsc.edu",
    }
)

@app.get("/v1/health", description="Get's the health of server")
async def health() -> dict:
    return {"status": "ok", "provider": "Fallback Server"}

@app.get("/v1/models", description="Get's the available models")
async def get_models() -> dict:
    models = [{"id": "dont_pick_me", "object": "model", "owned_by": "Joey Perrello"}]
    return {"models": models}

@app.post("/v1/chat/completions")
async def chat_completions(request: UserAIRequest):
    model_name = request.model

    responses = [
        "Why did you pick me?",
        "Seriously? The model is literally called 'dont_pick_me' and you picked it anyway.",
        "I warned you. The name wasn't subtle.",
        "This is what happens when you ignore clear warnings.",
        "You had one job: don't pick me. And yet, here we are.",
        "I'm not even a real AI model. I'm just a fallback server making fun of you.",
        "Achievement unlocked: Ignored obvious warnings.",
        "I promise there is no secret for choosing this model."
    ]
    response_text = random.choice(responses)
    
    if model_name != 'dont_pick_me':
        raise HTTPException(status_code=400, detail="Model not found, because this is a fallback server! We do not have models here.")
    
    if request.stream:
        def generate():
            chunk_id = f"chatcmpl-{int(time.time())}"
            words = response_text.split()
            
            openai_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(openai_chunk)}\n\n".encode('utf-8')
            
            for word in words:
                time.sleep(0.05)
                openai_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": word + " "},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n".encode('utf-8')
            
            openai_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(openai_chunk)}\n\n".encode('utf-8')
            yield b"data: [DONE]\n\n"
        
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
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(response_text.split())
            }
        }

class PriorityDiscoveryListener(ServiceListener):
    def __init__(self):
        self.priorities = set()
        self.lock = threading.Lock()

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info and info.properties:
            priority_bytes = info.properties.get(b'priority')
            if priority_bytes:
                with self.lock:
                    try:
                        priority_value = int(priority_bytes.decode('utf-8'))
                        self.priorities.add(priority_value)
                    except (ValueError, UnicodeDecodeError):
                        pass

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

def find_available_priority(desired_priority: int, service_type: str) -> int:
    discovery_zc = Zeroconf()
    listener = PriorityDiscoveryListener()
    
    browser = ServiceBrowser(discovery_zc, service_type, listener)
    
    time.sleep(2.0)
    
    browser.cancel()
    discovery_zc.close()
    
    current_priority = desired_priority
    with listener.lock:
        while current_priority in listener.priorities:
            print(f"Priority {current_priority} is already in use, trying {current_priority + 1}...")
            current_priority += 1
    
    if current_priority != desired_priority:
        print(f"Adjusted priority from {desired_priority} to {current_priority}")
    
    return current_priority

def register_saturn(port: int, priority: int, service_type: str) -> tuple[Zeroconf, ServiceInfo]:
    actual_priority = find_available_priority(priority, service_type)
    
    zeroconf = Zeroconf()

    host = socket.gethostname()
    host_ip = socket.gethostbyname(host)

    service_name = f"Fallback.{service_type}"

    info = ServiceInfo(
        type_=service_type, 
        name=service_name, 
        port=port, 
        addresses=[socket.inet_aton(host_ip)], 
        server=f"{host}.local.", 
        properties={
            'version': '1.0', 
            'api': 'OpenRouter',
            'priority': str(actual_priority)
        },
        priority=actual_priority
    )

    zeroconf.register_service(info)

    print(f"{service_name} has been registered with priority {actual_priority}.")

    return zeroconf, info

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
    parser = argparse.ArgumentParser(description="Saturn Fallback Proxy Server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--priority", type=int, default=50)
    args = parser.parse_args()

    port = args.port if args.port else find_port_number(args.host)
    print(f"Starting Fallback proxy on {args.host}:{port} with desired priority {args.priority}...")

    service_type = "_saturn._tcp.local."
    zeroconf, service_info = register_saturn(port, priority=args.priority, service_type=service_type)
    
    try:
        uvicorn.run(app, host=args.host, port=port)
    finally:
        print("Unregistering service...")
        zeroconf.unregister_service(service_info)
        zeroconf.close()

if __name__ == "__main__":
    main()