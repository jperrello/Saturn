import contextlib
import os
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
def serve(port=None, timeout=20.0):
    port = port or _free()
    log = open(f"/tmp/saturn-web-{port}.log", "wb")
    proc = subprocess.Popen(
        ["python3", "-m", "saturn", "web", "--port", str(port)],
        stdout=log, stderr=log, preexec_fn=os.setsid,
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
        yield origin
    finally:
        try: os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL)
