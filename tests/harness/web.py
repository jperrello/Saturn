import contextlib
import os
import secrets
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request


def _free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@contextlib.contextmanager
def serve(port=None, timeout=20.0, admin_token=None, env_extra=None):
    port = port or _free()
    tok = admin_token or secrets.token_urlsafe(24)
    log = open(f"/tmp/saturn-web-{port}.log", "wb")
    env = {**os.environ, "SATURN_ADMIN_TOKEN": tok, **(env_extra or {})}
    proc = subprocess.Popen(
        ["python3", "-m", "saturn", "web", "--port", str(port)],
        stdout=log, stderr=log, preexec_fn=os.setsid, env=env,
    )
    origin = f"http://127.0.0.1:{port}"
    deadline = time.time() + timeout
    ready = False
    while time.time() < deadline:
        try:
            urllib.request.urlopen(origin, timeout=1).read()
            ready = True
            break
        except (urllib.error.URLError, ConnectionResetError, OSError):
            time.sleep(0.3)
    if not ready:
        os.killpg(proc.pid, signal.SIGTERM)
        raise TimeoutError(f"saturn web did not come up on {port}")
    try:
        yield {"origin": origin, "token": tok}
    finally:
        try: os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try: proc.terminate()
            except ProcessLookupError: pass
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try: proc.kill()
                except ProcessLookupError: pass


def admin_request(origin, path, token, method="GET", body=None):
    import json
    url = f"{origin.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None: headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
        if not raw: return r.status, None
        return r.status, json.loads(raw)
