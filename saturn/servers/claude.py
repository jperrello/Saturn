import os
import json
import time
import logging
from fastapi import FastAPI, HTTPException
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from claude_agent_sdk.types import StreamEvent

from . import ChatRequest, sse, chunk, completion

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

os.environ.pop("CLAUDECODE", None)

MODELS = [
    {"id": "claude-code-opus", "object": "model", "owned_by": "anthropic"},
    {"id": "claude-code-sonnet", "object": "model", "owned_by": "anthropic"},
    {"id": "claude-code-haiku", "object": "model", "owned_by": "anthropic"},
]

MODEL_MAP = {
    "claude-code-opus": "opus",
    "claude-code-sonnet": "sonnet",
    "claude-code-haiku": "haiku",
}

app = FastAPI(
    title="Saturn Claude Code",
    description="Claude Code agentic server with OpenAI-compatible API",
    version="1.0",
)


@app.get("/v1/health")
async def health() -> dict:
    return {"status": "ok", "service": "claude-code", "deployment": "network"}


@app.get("/v1/models")
async def models() -> dict:
    return {"object": "list", "data": MODELS}


def _extract_prompt(request: ChatRequest) -> str:
    for msg in reversed(request.messages):
        if msg.role == "user" and msg.content:
            return msg.content
    return ""


def _make_options(backing: str, stream: bool = False) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=backing,
        permission_mode="bypassPermissions",
        max_turns=10,
        cwd="/Users/jperr/Documents/Saturn",
        include_partial_messages=stream,
    )


@app.post("/v1/chat/completions")
async def chat(request: ChatRequest):
    backing = MODEL_MAP.get(request.model)
    if not backing:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model}")

    prompt = _extract_prompt(request)
    if not prompt:
        raise HTTPException(status_code=400, detail="No user message found")

    logger.info(f"Query claude-code model={backing} prompt={prompt[:80]}")

    if request.stream:
        return _stream(request.model, backing, prompt)

    try:
        options = _make_options(backing)
        result_text = ""
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                result_text = msg.result or ""
                break
        return completion(
            request.model,
            {"role": "assistant", "content": result_text},
        )
    except Exception as e:
        logger.error(f"claude-agent-sdk error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _stream(model: str, backing: str, prompt: str):
    async def generate():
        chunk_id = f"chatcmpl-{int(time.time())}"
        first = True
        try:
            async for msg in query(prompt=prompt, options=_make_options(backing, stream=True)):
                if isinstance(msg, StreamEvent):
                    event = msg.event
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                d = {"content": text}
                                if first:
                                    d["role"] = "assistant"
                                    first = False
                                yield f"data: {json.dumps(chunk(chunk_id, model, d))}\n\n".encode("utf-8")
                    elif event.get("type") == "message_stop":
                        yield f"data: {json.dumps(chunk(chunk_id, model, {}, finish=True))}\n\n".encode("utf-8")
                        yield b"data: [DONE]\n\n"
                        return
                elif isinstance(msg, ResultMessage):
                    if first and msg.result:
                        d = {"role": "assistant", "content": msg.result}
                        yield f"data: {json.dumps(chunk(chunk_id, model, d))}\n\n".encode("utf-8")
                    yield f"data: {json.dumps(chunk(chunk_id, model, {}, finish=True))}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"
                    return
            if first:
                yield f"data: {json.dumps(chunk(chunk_id, model, {'role': 'assistant', 'content': ''}))}\n\n".encode("utf-8")
            yield f"data: {json.dumps(chunk(chunk_id, model, {}, finish=True))}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise

    return sse(generate())
