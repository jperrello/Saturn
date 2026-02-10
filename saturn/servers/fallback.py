import random
import asyncio
import time
import json
import logging
from fastapi import FastAPI, HTTPException

from . import ChatRequest, sse, chunk, completion

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("saturn.fallback")

app = FastAPI(
    title="Saturn Fallback",
    description="A mock fallback server for testing Saturn service discovery and failover logic.",
    version="2.0",
)

RESPONSES = [
    "Why did you pick me?",
    "Seriously? The model is literally called 'dont_pick_me' and you picked it anyway.",
    "I warned you. The name wasn't subtle.",
    "This is what happens when you ignore clear warnings.",
    "You had one job: don't pick me. And yet, here we are.",
    "I'm not even a real AI model. I'm just a fallback server making fun of you.",
    "Achievement unlocked: Ignored obvious warnings.",
    "I promise there is no secret for choosing this model."
]


@app.get("/v1/health")
async def health() -> dict:
    return {"status": "ok", "provider": "Fallback", "saturn": True}


@app.get("/v1/models")
async def models() -> dict:
    return {"object": "list", "data": [{"id": "dont_pick_me", "object": "model", "owned_by": "saturn"}]}


@app.post("/v1/chat/completions")
async def completions(request: ChatRequest):
    if request.model != "dont_pick_me":
        raise HTTPException(status_code=400, detail="Model not found. This is a fallback server!")

    text = random.choice(RESPONSES)

    if request.stream:
        async def generate():
            cid = f"chatcmpl-{int(time.time())}"
            yield f"data: {json.dumps(chunk(cid, request.model, {'role': 'assistant'}))}\n\n"
            for word in text.split():
                await asyncio.sleep(0.05)
                yield f"data: {json.dumps(chunk(cid, request.model, {'content': word + ' '}))}\n\n"
            yield f"data: {json.dumps(chunk(cid, request.model, {}, finish=True))}\n\n"
            yield "data: [DONE]\n\n"
        return sse(generate())

    return completion(
        request.model,
        {"role": "assistant", "content": text},
        {"prompt_tokens": 0, "completion_tokens": len(text.split()), "total_tokens": len(text.split())},
    )
