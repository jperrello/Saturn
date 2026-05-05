import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path


PEER_SRC = r'''
import json, os, time
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

NAME = os.environ["PEER_NAME"]
PORT = int(os.environ["PEER_PORT"])
STATE = os.environ["PEER_STATE_FILE"]
MODELS = json.loads(os.environ.get("PEER_MODELS", '["shared-model"]'))


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
        chunk = {"id": "x", "object": "chat.completion.chunk", "model": model,
                 "choices": [{"index": 0, "delta": {"role": "assistant",
                              "content": f"hello-from-{NAME}"}, "finish_reason": None}]}
        yield f"data: {json.dumps(chunk)}\n\n".encode()
        done = {"id": "x", "object": "chat.completion.chunk", "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 4, "total_tokens": 5}}
        yield f"data: {json.dumps(done)}\n\n".encode()
        yield b"data: [DONE]\n\n"

    if streaming:
        return StreamingResponse(_chunks(), media_type="text/event-stream")
    return {"id": "x", "object": "chat.completion", "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant",
                         "content": f"hello-from-{NAME}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 4, "total_tokens": 5}}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
'''


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def wait_up(url, deadline=10):
    end = time.time() + deadline
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return True
        except Exception:
            time.sleep(0.1)
    return False


def boot_peer(tmp, name, port, priority, models):
    state = Path(tmp) / f"{name}.state.json"
    state.write_text(json.dumps({"health_ok": True, "chat_500": False, "chat_delay_s": 0.0}))
    src = Path(tmp) / "peer.py"
    if not src.exists():
        src.write_text(PEER_SRC)
    env = {**os.environ,
           "PEER_NAME": name,
           "PEER_PORT": str(port),
           "PEER_STATE_FILE": str(state),
           "PEER_MODELS": json.dumps(models)}
    log = open(Path(tmp) / f"{name}.log", "wb")
    proc = subprocess.Popen([sys.executable, str(src)], env=env, stdout=log, stderr=log)
    if not wait_up(f"http://127.0.0.1:{port}/v1/health"):
        proc.terminate()
        sys.exit(f"{name} did not come up")
    return {"name": name, "host": "127.0.0.1", "port": port, "priority": priority,
            "models": models, "state_file": state, "proc": proc}


def set_state(peer, **kv):
    cur = json.loads(peer["state_file"].read_text())
    cur.update(kv)
    peer["state_file"].write_text(json.dumps(cur))


def last_meta(text):
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
    return None


def banner(s):
    print()
    print("=" * 72)
    print(s)
    print("=" * 72)


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    with tempfile.TemporaryDirectory(prefix="cbt4-") as tmp:
        banner("cbt.4 — client-side failover probe")
        print(f"  tmp={tmp}")

        a = boot_peer(tmp, "peer-a", free(), priority=10, models=["shared-model"])
        b = boot_peer(tmp, "peer-b", free(), priority=20, models=["shared-model"])
        print(f"  service-A  127.0.0.1:{a['port']}  priority=10")
        print(f"  service-B  127.0.0.1:{b['port']}  priority=20")

        try:
            from fastapi.testclient import TestClient
            import saturn.web as W

            W._discovered.clear()
            if hasattr(W, "_breakers"): W._breakers.clear()
            if hasattr(W, "_failover_state"): W._failover_state.clear()
            for p in (a, b):
                W._discovered[p["name"]] = {
                    "name": p["name"], "host": p["host"], "port": p["port"],
                    "status": "online", "priority": p["priority"],
                    "deployment": "network", "api_type": "openai",
                    "models": p["models"], "node_id": p["name"],
                }
            client = TestClient(W.app)

            convo = f"c-{uuid.uuid4().hex[:8]}"

            banner("baseline: both healthy → traffic on highest-priority (peer-a)")
            t0 = time.time()
            r = client.post("/api/system/chat",
                            headers={"X-Saturn-Conversation-Id": convo},
                            json={"model": "shared-model", "stream": True,
                                  "messages": [{"role": "user", "content": "hi"}]})
            dt = time.time() - t0
            print(f"  status={r.status_code}  elapsed={dt*1000:.0f}ms")
            assert r.status_code == 200, r.text[:300]
            assert "hello-from-peer-a" in r.text, "expected peer-a to serve baseline"
            print("  body contains 'hello-from-peer-a' ✓")

            banner("inject fault: peer-a → 503 on /v1/chat/completions")
            set_state(a, chat_500=True)
            print("  peer-a state: chat_500=True (simulates 5xx on active request)")

            banner("client retry on same conversation → must switch to peer-b in <2s")
            convo2 = f"c-{uuid.uuid4().hex[:8]}"
            t0 = time.time()
            r2 = client.post("/api/system/chat",
                             headers={"X-Saturn-Conversation-Id": convo2},
                             json={"model": "shared-model", "stream": True,
                                   "messages": [{"role": "user", "content": "hi"}]})
            dt = time.time() - t0
            print(f"  status={r2.status_code}  elapsed={dt*1000:.0f}ms (cap=2000ms)")
            assert r2.status_code == 200, r2.text[:400]
            assert "hello-from-peer-b" in r2.text, "expected switch to peer-b"
            assert dt < 2.0, f"switch latency budget blown: {dt:.2f}s"
            print("  body contains 'hello-from-peer-b' ✓")
            print("  switch latency under 2s ✓")

            banner("saturn_meta.routing.events — receipt of the switch")
            meta = last_meta(r2.text)
            if not meta:
                print("  (no saturn_meta on stream tail — cbt.4.0 lift required)")
                sys.exit(2)
            events = (meta.get("routing") or {}).get("events") or []
            print(json.dumps({"routing": meta.get("routing"),
                              "service": meta.get("service"),
                              "schema_version": meta.get("schema_version")}, indent=2))
            assert events, "routing.events must be non-empty after a switch"
            e0 = events[0]
            assert e0.get("from") == "peer-a" and e0.get("to") == "peer-b", e0
            assert e0.get("reason") in ("active_5xx", "health_timeout"), e0
            print("  routing.events[0] from=peer-a to=peer-b ✓")
            print(f"  reason={e0.get('reason')!r}  at={e0.get('at')!r}")

            banner("sticky: recover peer-a → traffic stays on peer-b")
            set_state(a, chat_500=False, health_ok=True)
            r3 = client.post("/api/system/chat",
                             headers={"X-Saturn-Conversation-Id": convo2},
                             json={"model": "shared-model", "stream": True,
                                   "messages": [{"role": "user", "content": "hi"}]})
            assert "hello-from-peer-b" in r3.text, "stickiness violated"
            print("  body still contains 'hello-from-peer-b' after peer-a recovery ✓")

            banner("model affinity: request a model no peer advertises → fail loud")
            r4 = client.post("/api/system/chat",
                             headers={"X-Saturn-Conversation-Id": f"c-{uuid.uuid4().hex[:6]}"},
                             json={"model": "ghost-model-xyz", "stream": True,
                                   "messages": [{"role": "user", "content": "hi"}]})
            print(f"  status={r4.status_code}")
            print(f"  body[:200]={r4.text[:200]!r}")
            assert r4.status_code in (404, 502), r4.status_code
            assert "ghost-model-xyz" in r4.text.lower(), "error must name the requested model"
            print("  failed loud with model name in body ✓")

            banner("PASS — cbt.4 falsifiable bullets all green")
            sys.exit(0)
        finally:
            for p in (a, b):
                try: p["proc"].terminate()
                except Exception: pass
            for p in (a, b):
                try: p["proc"].wait(timeout=3)
                except Exception:
                    try: p["proc"].kill()
                    except Exception: pass


if __name__ == "__main__":
    main()
