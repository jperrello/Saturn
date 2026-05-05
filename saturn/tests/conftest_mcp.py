"""Shared fake-MCP-server fixture for cbt.2.c.* contracts.

Spawns a real `mcp.server.FastMCP` instance in a subprocess speaking the
streamable-HTTP transport at `http://127.0.0.1:<port>/mcp`. Per-test
behavior is controlled via env vars read at child startup:

  FAKE_MCP_PORT     int  required
  FAKE_MCP_HANG     float (default 0)   sleep N seconds inside echo() before returning
  FAKE_MCP_BLOB_MB  int   (default 0)   return N MiB of "x" instead of echoing

The fixture also rewrites `saturn.mcp_client.CONFIG_PATH` to a tmp file
listing this fake server under name "fake-mcp", so callers can simply do
`MCPClientManager().call("fake-mcp", "echo", {"text": "hi"})`.

NO MOCKS. Real subprocess, real FastMCP, real streamable-HTTP transport.
"""

import json
import os
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


FAKE_MCP_SRC = textwrap.dedent('''
    import os, time
    from mcp.server import FastMCP

    PORT = int(os.environ["FAKE_MCP_PORT"])
    HANG = float(os.environ.get("FAKE_MCP_HANG", "0"))
    BLOB_MB = int(os.environ.get("FAKE_MCP_BLOB_MB", "0"))

    m = FastMCP("brutus-fake", host="127.0.0.1", port=PORT, stateless_http=True)

    @m.tool()
    def echo(text: str) -> str:
        if HANG > 0:
            time.sleep(HANG)
        if BLOB_MB > 0:
            return "x" * (BLOB_MB * 1024 * 1024)
        return text

    if __name__ == "__main__":
        m.run(transport="streamable-http")
''')


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait_up(url: str, deadline_s: float = 10.0) -> bool:
    end = time.time() + deadline_s
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except urllib.error.HTTPError:
            return True  # any HTTP response means the server is listening
        except (urllib.error.URLError, ConnectionResetError, OSError):
            time.sleep(0.1)
    return False


def make_fake_mcp(tmp_path: Path, *, hang: float = 0.0, blob_mb: int = 0):
    """Returns a context-manager-ish dict {url, port, proc, log_path}.

    Caller is responsible for terminating proc on teardown (use fake_mcp
    fixture instead unless you really want manual control).
    """
    src = tmp_path / "fake_mcp.py"
    src.write_text(FAKE_MCP_SRC)
    port = _free_port()
    log = open(tmp_path / "fake_mcp.log", "wb")
    env = {
        **os.environ,
        "FAKE_MCP_PORT": str(port),
        "FAKE_MCP_HANG": str(hang),
        "FAKE_MCP_BLOB_MB": str(blob_mb),
    }
    proc = subprocess.Popen([sys.executable, str(src)], env=env,
                            stdout=log, stderr=log)
    base = f"http://127.0.0.1:{port}/mcp"
    if not _wait_up(base, deadline_s=15.0):
        try: proc.terminate()
        except Exception: pass
        log.close()
        raise RuntimeError(f"fake MCP did not come up on port {port}; see {tmp_path / 'fake_mcp.log'}")
    return {"url": base, "port": port, "proc": proc,
            "log_path": tmp_path / "fake_mcp.log"}


@pytest.fixture
def fake_mcp(tmp_path, request, monkeypatch):
    """Spin a fake MCP server. Per-test config via marker:

        @pytest.mark.fake_mcp(hang=30, blob_mb=0)
    """
    marker = request.node.get_closest_marker("fake_mcp")
    cfg = (marker.kwargs if marker else {}) or {}
    info = make_fake_mcp(tmp_path, hang=cfg.get("hang", 0.0), blob_mb=cfg.get("blob_mb", 0))

    # Point saturn.mcp_client at this server under name "fake-mcp".
    import saturn.mcp_client as m
    cfg_path = tmp_path / "mcp-servers.json"
    cfg_path.write_text(json.dumps([{"name": "fake-mcp", "url": info["url"]}]))
    monkeypatch.setattr(m, "CONFIG_PATH", cfg_path)

    try:
        yield info
    finally:
        try: info["proc"].terminate()
        except Exception: pass
        try: info["proc"].wait(timeout=3)
        except Exception:
            try: info["proc"].kill()
            except Exception: pass
