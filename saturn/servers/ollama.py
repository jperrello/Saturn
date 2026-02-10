import time
import json
import logging
from fastapi import FastAPI, HTTPException
import requests
from typing import List, Dict

from . import ChatRequest, sse, chunk, completion

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"

app = FastAPI(
    title="Saturn Ollama",
    description="Ollama proxy with OpenAI-compatible API translation",
    version="2.0",
)



@app.get("/v1/health")
async def health() -> dict:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=2)
        if response.status_code == 200:
            return {"status": "ok", "provider": "Ollama", "saturn": True}
    except Exception:
        pass
    raise HTTPException(status_code=503, detail="Ollama server is not reachable")


@app.get("/v1/models")
async def get_models() -> dict:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [
                {"id": model.get("name"), "object": "model", "owned_by": "ollama"}
                for model in data.get("models", [])
            ]
            if models:
                return {"object": "list", "data": models}
    except Exception as e:
        logger.error(f"Error fetching models from Ollama: {e}")
    raise HTTPException(status_code=503, detail="Could not fetch models from Ollama server.")


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    logger.info(f"Received request for model: {request.model}")

    payload = {
        "model": request.model,
        "messages": [m.model_dump(exclude_none=True) for m in request.messages],
        "stream": request.stream,
    }

    if request.max_tokens:
        payload["options"] = {"num_predict": request.max_tokens}
    if request.tools is not None:
        payload["tools"] = request.tools

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
                has_tool_calls = False

                try:
                    for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            ollama_chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if ollama_chunk.get("done"):
                            reason = "tool_calls" if has_tool_calls else "stop"
                            done_chunk = chunk(chunk_id, request.model, {}, finish=True)
                            done_chunk["choices"][0]["finish_reason"] = reason
                            yield f"data: {json.dumps(done_chunk)}\n\n".encode('utf-8')
                            yield b"data: [DONE]\n\n"
                        else:
                            msg = ollama_chunk.get("message", {})
                            content = msg.get("content", "")
                            role = msg.get("role")
                            calls = msg.get("tool_calls")

                            delta = {}
                            if first_chunk and role:
                                delta["role"] = role
                                first_chunk = False
                            if content:
                                delta["content"] = content
                            if calls:
                                delta["tool_calls"] = calls
                                has_tool_calls = True

                            if delta:
                                yield f"data: {json.dumps(chunk(chunk_id, request.model, delta))}\n\n".encode('utf-8')
                except Exception as e:
                    logger.error(f"Error in stream generation: {type(e).__name__}: {str(e)}")
                    raise
                finally:
                    response.close()

            return sse(generate())

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            raise HTTPException(status_code=502, detail=f"Ollama returned non-JSON response: {response.text[:500]}")

        msg = data.get("message", {})
        message = {"role": msg.get("role", "assistant"), "content": msg.get("content", "")}
        calls = msg.get("tool_calls")
        reason = "stop"
        if calls:
            message["tool_calls"] = calls
            reason = "tool_calls"
        return completion(
            request.model,
            message,
            {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            },
            finish_reason=reason,
        )

    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Ollama request timed out")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ollama connection error: {str(e)}")
