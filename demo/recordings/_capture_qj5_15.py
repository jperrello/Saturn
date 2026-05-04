import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


MIN_PASSWORD = "harness-fixture-pw-min-12chars"
MODEL = "qwen2.5:0.5b"
PROMPT = "Reply with exactly: hello world."
SYSTEM = "You are a deterministic test assistant. Answer concisely."
PARAMS = {"max_tokens": 50, "temperature": 0.0, "top_p": 0.01}


def _free():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def _ping(url):
    try: urllib.request.urlopen(url, timeout=2).read(); return True
    except Exception: return False


def boot(tmp):
    port = _free()
    admin = "qj515-" + secrets.token_urlsafe(24)
    runner = "qj515r-" + secrets.token_urlsafe(24)
    env = {
        "PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
        "SATURN_ADMIN_TOKEN": admin, "SATURN_RUNNER_TOKEN": runner,
        "SATURN_ADMIN_PASSWORD": MIN_PASSWORD,
        "SATURN_DATA_DIR": f"{tmp}/data",
        "SATURN_SERVICES_DIR": f"{tmp}/services",
        "SATURN_BIND_HOST": "127.0.0.1",
    }
    log = open(f"{tmp}/saturn-web.log", "wb")
    proc = subprocess.Popen(
        [sys.executable, "-m", "saturn", "web", "--port", str(port)],
        env=env, stdout=log, stderr=log,
    )
    origin = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline and not _ping(origin):
        if proc.poll() is not None:
            sys.stderr.write(open(f"{tmp}/saturn-web.log").read())
            sys.exit("saturn web exited during boot")
        time.sleep(0.3)
    if not _ping(origin): proc.terminate(); sys.exit("saturn web never came up")
    return proc, origin, admin


def install_service(tmp):
    name = "qj515-probe"
    sd = f"{tmp}/services"
    os.makedirs(sd, exist_ok=True)
    open(f"{sd}/{name}.toml", "w").write(
        f'name = "{name}"\n'
        f'deployment = "local"\napi_type = "ollama"\npriority = 50\n'
        f'[upstream]\nbase_url = "http://localhost:11434/v1"\n'
        f'[server]\nport = 0\n[beacon]\nenabled = false\n'
    )
    return name


def post_chat(origin, token, service):
    body = {
        "service": service, "model": MODEL, "stream": True,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user",   "content": PROMPT}],
        **PARAMS,
    }
    req = urllib.request.Request(
        f"{origin}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"), body


def find_meta(stream_text):
    for line in reversed(stream_text.splitlines()):
        if not line.startswith("data:"): continue
        p = line[5:].strip()
        if p in ("", "[DONE]"): continue
        try: obj = json.loads(p)
        except Exception: continue
        if isinstance(obj, dict) and "saturn_meta" in obj:
            return obj["saturn_meta"]
    return None


def render_diff(req, meta):
    applied = (meta or {}).get("applied") or {}
    diff = (meta or {}).get("diff") or {}
    rows = [
        ("model",         req["model"],                str(applied.get("model", "—"))),
        ("max_tokens",    str(req.get("max_tokens")),  str(applied.get("max_tokens", "—"))),
        ("temperature",   str(req.get("temperature")), str(applied.get("temperature", "—"))),
        ("top_p",         str(req.get("top_p")),       str(applied.get("top_p", "—"))),
        ("system_prompt", "<inline>",                  applied.get("system_prompt_sha256", "—")[:16] + "…"
                                                       if applied.get("system_prompt_sha256") else "—"),
        ("finish_reason", "—",                         str(applied.get("finish_reason", "—"))),
    ]
    out = ["", f"  {'field':<16} {'configured':<32} {'applied':<32}",
              f"  {'-'*16} {'-'*32} {'-'*32}"]
    for k, c, a in rows:
        out.append(f"  {k:<16} {c:<32} {a:<32}")
    if diff.get("coerced"):
        out.append(f"\n  diff.coerced: {', '.join(diff['coerced'])}")
    return "\n".join(out)


def main():
    with tempfile.TemporaryDirectory(prefix="qj515-") as tmp:
        proc, origin, token = boot(tmp)
        try:
            svc = install_service(tmp)
            stream, req = post_chat(origin, token, svc)
            meta = find_meta(stream)
            print(f"=== /api/chat stream → tail (last 600 chars) ===")
            print(stream[-600:])
            print()
            print("=== saturn_meta envelope ===")
            print(json.dumps(meta, indent=2) if meta else
                  "  (absent — receipt envelope not yet wired; "
                  "qj5.15 implementation pending)")
            print()
            print("=== Configured vs Applied (gullivan Pattern 1+2) ===")
            print(render_diff(req, meta))
            sys.exit(0)
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill()


if __name__ == "__main__":
    main()
