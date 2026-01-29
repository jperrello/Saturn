import argparse
import socket
import time
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
import requests
from pydantic import BaseModel
from typing import Literal, List, Dict

from .discovery import SaturnAdvertiser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"


def get_ollama_models() -> List[Dict]:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = []
            for model in data.get("models", []):
                models.append({
                    "id": model.get("name"),
                    "object": "model",
                    "owned_by": "ollama",
                })
            return models
    except Exception as e:
        logger.error(f"Error fetching models from Ollama: {e}")
    return []


def get_model_names() -> List[str]:
    models = get_ollama_models()
    return [m["id"] for m in models]


app = FastAPI(
    title="Saturn Ollama",
    description="Saturn Ollama server with mDNS registration (_saturn._tcp)",
    summary="Ollama proxy with MCP-compatible discovery",
    version="2.0",
    contact={
        "name": "Joey Perrello",
        "url": "https://jperrello.netlify.app/",
        "email": "jperrell@ucsc.edu",
    })


class CurrentChatContent(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class UserAIRequest(BaseModel):
    model: str
    messages: list[CurrentChatContent]
    max_tokens: int | None = None
    stream: bool = False


@app.get("/v1/health")
async def health() -> dict:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            return {"status": "ok", "provider": "Ollama", "saturn": True}
    except Exception:
        pass
    raise HTTPException(status_code=503, detail="Ollama server is not reachable")


@app.get("/v1/models")
async def get_models() -> dict:
    models = get_ollama_models()
    if not models:
        raise HTTPException(status_code=503, detail="Could not fetch models from Ollama server.")
    return {"models": models}


@app.post("/v1/chat/completions")
async def chat_completions(request: UserAIRequest):
    logger.info(f"Received request for model: {request.model}")
    logger.info(f"Messages count: {len(request.messages)}, stream: {request.stream}")

    ollama_payload = {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "stream": request.stream,
    }

    if request.max_tokens:
        ollama_payload["options"] = {"num_predict": request.max_tokens}

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=ollama_payload,
            timeout=120,
            stream=request.stream
        )

        if response.status_code != 200:
            logger.error(f"Ollama error response: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama API error: {response.text}"
            )

        if request.stream:
            # ollama streams json objects one per line, openai uses sse with "data: {json}\n\n"
            # we translate on the fly, also delta.role only goes in the first chunk per openai spec
            def generate():
                chunk_id = f"chatcmpl-{int(time.time())}"
                first_chunk = True

                try:
                    for line in response.iter_lines():
                        if line:
                            try:
                                ollama_chunk = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            if ollama_chunk.get("done"):
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
                            else:
                                content = ollama_chunk.get("message", {}).get("content", "")
                                role = ollama_chunk.get("message", {}).get("role")

                                delta = {}
                                if first_chunk and role:
                                    delta["role"] = role
                                    first_chunk = False

                                if content:
                                    delta["content"] = content

                                if delta:
                                    openai_chunk = {
                                        "id": chunk_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": request.model,
                                        "choices": [{
                                            "index": 0,
                                            "delta": delta,
                                            "finish_reason": None
                                        }]
                                    }
                                    yield f"data: {json.dumps(openai_chunk)}\n\n".encode('utf-8')
                except Exception as e:
                    logger.error(f"Error in stream generation: {type(e).__name__}: {str(e)}")
                    raise
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
                data = response.json()
            except requests.exceptions.JSONDecodeError:
                raise HTTPException(
                    status_code=502,
                    detail=f"Ollama returned non-JSON response: {response.text[:500]}"
                )

            message = data.get("message", {})
            content = message.get("content", "")
            role = message.get("role", "assistant")

            result = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": role,
                            "content": content
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                }
            }

            logger.info(f"Returning response with content length: {len(content)}")
            return result

    except requests.Timeout:
        logger.error("Ollama request timed out")
        raise HTTPException(status_code=504, detail="Ollama request timed out")
    except requests.RequestException as e:
        logger.error(f"Ollama connection error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ollama connection error: {str(e)}")


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
    parser = argparse.ArgumentParser(description="Saturn Ollama Server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--priority", type=int, default=50)
    args = parser.parse_args()

    port = args.port if args.port else find_port_number(args.host)
    logger.info(f"Starting Ollama proxy on {args.host}:{port} with priority {args.priority}")

    model_names = get_model_names()
    logger.info(f"Available models: {', '.join(model_names) if model_names else 'none detected'}")

    advertiser = SaturnAdvertiser(
        name="Ollama",
        port=port,
        deployment="network",
        api_type="ollama",
        priority=args.priority,
        models=model_names,
        capabilities=["chat", "code"],
        context=4096,
        cost="free",
    )
    advertiser.register()

    try:
        uvicorn.run(app, host=args.host, port=port)
    finally:
        logger.info("Shutting down...")
        advertiser.unregister()


if __name__ == "__main__":
    main()
