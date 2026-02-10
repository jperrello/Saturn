import json
import time
from pydantic import BaseModel
from typing import Any, Optional, List
from fastapi.responses import StreamingResponse


class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    tool_call_id: Optional[str] = None




class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    stream: bool = False
    temperature: Optional[float] = None
    tools: Optional[List[dict]] = None
    tool_choice: Optional[Any] = None


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse(generator):
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


def chunk(id, model, delta, finish=False):
    return {
        "id": id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": "stop" if finish else None}],
    }


def completion(model, message, usage=None, finish_reason="stop"):
    result = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
    }
    if usage:
        result["usage"] = usage
    return result


def proxy_sse(response):
    def generate():
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                if decoded.startswith("data: "):
                    data = decoded[6:]
                    if data == "[DONE]":
                        yield b"data: [DONE]\n\n"
                        break
                    try:
                        parsed = json.loads(data)
                        yield f"data: {json.dumps(parsed)}\n\n".encode("utf-8")
                    except json.JSONDecodeError:
                        continue
        finally:
            response.close()
    return sse(generate())
