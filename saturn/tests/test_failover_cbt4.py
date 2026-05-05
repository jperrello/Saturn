"""Saturn-cbt.4 — client-side failover (FULL contract).

Brutus contract per RUN_BRIEF_MAY05.md §B.2 + clarifications received from Joey:

  surface  = POST /api/system/chat   (saturn/web.py:1054)
  sticky   = X-Saturn-Conversation-Id header (preferred) /
             body.conversation_id (fallback) /
             30s per-process hysteresis when both absent
  cbt.4.0  = saturn_meta envelope MUST be lifted to /api/system/chat
             (with new key `routing.events`)

Acceptance bullets (all four falsifiable):

  1. Timeout-driven switch: when current peer's /v1/health fails 2 times
     consecutively OR an active chat request returns HTTP 5xx, the next-priority
     peer takes over within 2s wall-clock end-to-end.

  2. Sticky session: once a conversation has switched off peer A, subsequent
     requests on that same conversation MUST stay on the new peer even when
     peer A recovers. Stickiness ends only when the new peer also fails (then
     advance to next-priority).

  3. Per-model affinity: the runner only switches to a peer that advertises
     the requested model. If no peer advertises the model, /api/system/chat
     fails loud with HTTP 502 and an error body that names the requested model.

  4. Routing receipt: saturn_meta.routing.events is a list with at least one
     entry per switch in this turn, each entry shaped:
        {"from": <peer-name>, "to": <peer-name>,
         "reason": "health_timeout" | "active_5xx",
         "at": <unix-seconds float>}

NO MOCKS. Two real FastAPI peers spun via subprocess on free ports, injected
into saturn.web._discovered. The "client" under test is the in-process
saturn.web.app exercised by TestClient.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest


pytestmark = pytest.mark.timeout(120)


# --- peer subprocess source code (written to tmp + spawned) -----------------
PEER_SRC = r'''
import json, os, time
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

NAME = os.environ["PEER_NAME"]
PORT = int(os.environ["PEER_PORT"])
STATE = os.environ["PEER_STATE_FILE"]
MODELS = json.loads(os.environ.get("PEER_MODELS", '["test-model-a"]'))


def _state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {"health_ok": True, "chat_500": False, "chat_delay_s": 0.0}


app = FastAPI()


@app.get("/v1/health")
def health():
    s = _state()
    if not s.get("health_ok", True):
        return JSONResponse({"status": "down"}, status_code=503)
    return {"status": "ok", "service": NAME, "saturn": True, "models_cached": len(MODELS)}


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": m, "object": "model", "owned_by": NAME} for m in MODELS]}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    s = _state()
    if s.get("chat_delay_s"):
        time.sleep(float(s["chat_delay_s"]))
    if s.get("chat_500"):
        return JSONResponse({"error": f"{NAME} is sick"}, status_code=503)
    body = await req.json()
    model = body.get("model", "?")
    streaming = bool(body.get("stream"))

    def _chunks():
        chunk = {
            "id": "x", "object": "chat.completion.chunk", "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": f"hello-from-{NAME}"},
                         "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk)}\n\n".encode()
        done = {
            "id": "x", "object": "chat.completion.chunk", "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 4, "total_tokens": 5},
        }
        yield f"data: {json.dumps(done)}\n\n".encode()
        yield b"data: [DONE]\n\n"

    if streaming:
        return StreamingResponse(_chunks(), media_type="text/event-stream")
    return {
        "id": "x", "object": "chat.completion", "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": f"hello-from-{NAME}"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 4, "total_tokens": 5},
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
'''


def _free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait_up(url, deadline_s=10):
    end = time.time() + deadline_s
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return True
        except Exception:
            time.sleep(0.1)
    return False


@pytest.fixture
def peers(tmp_path):
    src = tmp_path / "peer.py"
    src.write_text(PEER_SRC)
    procs = []
    descriptors = []
    try:
        for name, models in [("peer-a", ["shared-model"]), ("peer-b", ["shared-model"])]:
            port = _free()
            state_file = tmp_path / f"{name}.state.json"
            state_file.write_text(json.dumps({"health_ok": True, "chat_500": False, "chat_delay_s": 0.0}))
            env = {**os.environ,
                   "PEER_NAME": name,
                   "PEER_PORT": str(port),
                   "PEER_STATE_FILE": str(state_file),
                   "PEER_MODELS": json.dumps(models)}
            log = open(tmp_path / f"{name}.log", "wb")
            proc = subprocess.Popen([sys.executable, str(src)], env=env, stdout=log, stderr=log)
            procs.append(proc)
            assert _wait_up(f"http://127.0.0.1:{port}/v1/health"), \
                f"{name} did not come up; see {tmp_path / f'{name}.log'}"
            descriptors.append({"name": name, "host": "127.0.0.1", "port": port,
                                "models": models, "state_file": state_file,
                                "priority": 50 if name == "peer-a" else 60})
        yield descriptors
    finally:
        for p in procs:
            try: p.terminate()
            except Exception: pass
        for p in procs:
            try: p.wait(timeout=3)
            except Exception:
                try: p.kill()
                except Exception: pass


def _set_state(desc, **kv):
    cur = json.loads(desc["state_file"].read_text())
    cur.update(kv)
    desc["state_file"].write_text(json.dumps(cur))


@pytest.fixture
def app_client(peers, monkeypatch):
    from fastapi.testclient import TestClient
    import saturn.web as W
    admin_token = "cbt4-admin-" + secrets.token_urlsafe(16)
    monkeypatch.setenv("SATURN_ADMIN_TOKEN", admin_token)
    W._discovered.clear()
    W._breakers.clear()
    if hasattr(W, "_failover_state"):
        W._failover_state.clear()
    for d in peers:
        W._discovered[d["name"]] = {
            "name": d["name"], "host": d["host"], "port": d["port"],
            "status": "online", "priority": d["priority"],
            "deployment": "network", "api_type": "openai",
            "models": d["models"], "node_id": d["name"],
        }
    client = TestClient(W.app)
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    yield client, peers
    W._discovered.clear()


def _last_meta(text):
    for line in reversed(text.splitlines()):
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if isinstance(obj, dict) and "saturn_meta" in obj:
            return obj["saturn_meta"]
    raise AssertionError(
        "no saturn_meta on /api/system/chat. cbt.4.0 lift required. "
        "Stream tail:\n" + text[-1500:]
    )


def _post_chat(client, model="shared-model", convo=None):
    headers = {}
    if convo:
        headers["X-Saturn-Conversation-Id"] = convo
    return client.post(
        "/api/system/chat",
        headers=headers,
        json={"model": model, "stream": True,
              "messages": [{"role": "user", "content": "hi"}]},
    )


# --- (1) Active 5xx triggers switch within 2s -------------------------------

def test_active_5xx_switches_within_2s_and_records_event(app_client):
    client, peers = app_client
    a, b = peers[0], peers[1]
    _set_state(a, chat_500=True)

    convo = f"c-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    r = _post_chat(client, convo=convo)
    elapsed = time.time() - t0

    assert r.status_code == 200, f"expected 200 after switch; got {r.status_code}: {r.text[:300]}"
    assert "hello-from-peer-b" in r.text, (
        f"response must come from peer-b after peer-a 5xx; got body: {r.text[:400]}"
    )
    assert elapsed < 2.0, f"switch latency must be <2s; took {elapsed:.2f}s"

    meta = _last_meta(r.text)
    events = (meta.get("routing") or {}).get("events") or []
    assert events, f"saturn_meta.routing.events must be non-empty after a switch; meta={meta!r}"
    e = events[0]
    assert e.get("from") == "peer-a" and e.get("to") == "peer-b", (
        f"first event must record from=peer-a → to=peer-b; got {e!r}"
    )
    assert e.get("reason") == "active_5xx", (
        f"reason must be 'active_5xx' for an upstream 5xx switch; got {e.get('reason')!r}"
    )
    assert isinstance(e.get("at"), (int, float)) and e["at"] > 0, (
        f"event.at must be a unix-seconds number; got {e.get('at')!r}"
    )


# --- (2) Two consecutive /v1/health fails trigger switch --------------------

def test_two_consecutive_health_failures_trigger_switch(app_client):
    client, peers = app_client
    a, b = peers[0], peers[1]
    _set_state(a, health_ok=False)

    convo = f"c-{uuid.uuid4().hex[:8]}"
    # First two requests prime the health-fail counter to 2 consecutive misses.
    # Implementation MAY do it pre-flight on each chat call.
    t0 = time.time()
    r1 = _post_chat(client, convo=convo)
    r2 = _post_chat(client, convo=convo)
    elapsed = time.time() - t0

    assert r1.status_code == 200 and r2.status_code == 200
    assert "hello-from-peer-b" in r2.text, (
        f"after 2 consecutive /v1/health failures on peer-a, traffic must move to peer-b; "
        f"got r2 body: {r2.text[:400]}"
    )
    assert elapsed < 4.0, f"two health-driven decisions must complete in <4s; took {elapsed:.2f}s"

    meta = _last_meta(r2.text)
    events = (meta.get("routing") or {}).get("events") or []
    reasons = [e.get("reason") for e in events]
    assert "health_timeout" in reasons, (
        f"saturn_meta.routing.events must record at least one reason='health_timeout' "
        f"after 2 consecutive /v1/health 5xx; got events={events!r}"
    )


# --- (3) Sticky: don't oscillate back when original recovers ----------------

def test_sticky_does_not_oscillate_on_peer_a_recovery(app_client):
    client, peers = app_client
    a, b = peers[0], peers[1]
    convo = f"c-{uuid.uuid4().hex[:8]}"

    # Force a switch.
    _set_state(a, chat_500=True)
    r1 = _post_chat(client, convo=convo)
    assert "hello-from-peer-b" in r1.text, "setup: expected switch to peer-b"

    # Recover peer-a.
    _set_state(a, chat_500=False, health_ok=True)

    # Subsequent requests on same conversation MUST stay on peer-b.
    r2 = _post_chat(client, convo=convo)
    r3 = _post_chat(client, convo=convo)

    assert "hello-from-peer-b" in r2.text, (
        f"after switch + peer-a recovery, traffic must remain sticky on peer-b for the same "
        f"conversation; got r2: {r2.text[:400]}"
    )
    assert "hello-from-peer-b" in r3.text, (
        f"sticky must persist across multiple requests on the same conversation; "
        f"got r3: {r3.text[:400]}"
    )

    meta = _last_meta(r3.text)
    events = (meta.get("routing") or {}).get("events") or []
    # No NEW switch should be recorded on r3 (no oscillation back to peer-a).
    back_to_a = [e for e in events if e.get("to") == "peer-a"]
    assert not back_to_a, (
        f"sticky violation: detected a switch back to peer-a after recovery; events={events!r}"
    )


# --- (4) Per-model affinity: fail loud when no peer has the model -----------

def test_unknown_model_fails_loud_with_helpful_error(app_client):
    client, peers = app_client
    convo = f"c-{uuid.uuid4().hex[:8]}"
    r = _post_chat(client, model="nonexistent-ghost-model-xyz", convo=convo)
    assert r.status_code in (404, 502), (
        f"requesting a model no peer advertises must fail loud (404 or 502), not silently route; "
        f"got status={r.status_code}, body={r.text[:300]}"
    )
    body = r.text.lower()
    assert "nonexistent-ghost-model-xyz" in body, (
        f"error body must name the requested model so the user knows what to fix; "
        f"got body: {r.text[:400]}"
    )
