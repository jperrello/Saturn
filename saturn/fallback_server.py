import argparse
import random
import socket
import time
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
from pydantic import BaseModel
from typing import Literal

from .discovery import SaturnAdvertiser

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("saturn.fallback")


class CurrentChatContent(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class UserAIRequest(BaseModel):
    model: str
    messages: list[CurrentChatContent]
    max_tokens: int | None = None
    stream: bool = False


app = FastAPI(
    title="Saturn Fallback",
    description="A mock fallback server for testing Saturn service discovery and failover logic.",
    version="2.0",
)


@app.get("/v1/health")
async def health() -> dict:
    return {"status": "ok", "provider": "Fallback", "saturn": True}


@app.get("/v1/models")
async def get_models() -> dict:
    models = [{"id": "dont_pick_me", "object": "model", "owned_by": "saturn"}]
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

    if model_name != "dont_pick_me":
        raise HTTPException(status_code=400, detail="Model not found. This is a fallback server!")

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
            yield f"data: {json.dumps(openai_chunk)}\n\n".encode("utf-8")

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
                yield f"data: {json.dumps(openai_chunk)}\n\n".encode("utf-8")

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
            yield f"data: {json.dumps(openai_chunk)}\n\n".encode("utf-8")
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
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(response_text.split())
            }
        }


def find_port_number(host: str, start_port: int = 8080) -> int:
    port = start_port
    while port < 65535:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            port += 1
    raise RuntimeError("No available port found")


def main():
    parser = argparse.ArgumentParser(description="Saturn Fallback Server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--priority", type=int, default=99)
    args = parser.parse_args()

    port = args.port if args.port else find_port_number(args.host)
    logger.info(f"Starting Fallback server on {args.host}:{port} with priority {args.priority}")

    advertiser = SaturnAdvertiser(
        name="Fallback",
        port=port,
        models=["dont_pick_me"],
        capabilities=["chat"],
        context=0,
        cost="free",
        priority=args.priority,
        mcp="none",
    )
    advertiser.register()

    try:
        uvicorn.run(app, host=args.host, port=port)
    finally:
        logger.info("Shutting down...")
        advertiser.unregister()


if __name__ == "__main__":
    main()
