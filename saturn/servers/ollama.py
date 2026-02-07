import time
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import requests
from pydantic import BaseModel
from typing import Literal, List, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"


def get_ollama_models() -> List[Dict]:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [
                {"id": model.get("name"), "object": "model", "owned_by": "ollama"}
                for model in data.get("models", [])
            ]
    except Exception as e:
        logger.error(f"Error fetching models from Ollama: {e}")
    return []


app = FastAPI(
    title="Saturn Ollama",
    description="Ollama proxy with OpenAI-compatible API translation",
    version="2.0",
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
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
    return {"object": "list", "data": models}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    logger.info(f"Received request for model: {request.model}")

    payload = {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "stream": request.stream,
    }

    if request.max_tokens:
        payload["options"] = {"num_predict": request.max_tokens}

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=120,
            stream=request.stream
        )

        if response.status_code != 200:
            logger.error(f"Ollama error response: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=f"Ollama API error: {response.text}")

        if request.stream:
            def generate():
                chunk_id = f"chatcmpl-{int(time.time())}"
                first_chunk = True

                try:
                    for line in response.iter_lines():
                        if not line:
                            continue
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
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
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
                                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}]
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
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
            )

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            raise HTTPException(status_code=502, detail=f"Ollama returned non-JSON response: {response.text[:500]}")

        message = data.get("message", {})
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {"role": message.get("role", "assistant"), "content": message.get("content", "")},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            }
        }

    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Ollama request timed out")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ollama connection error: {str(e)}")
