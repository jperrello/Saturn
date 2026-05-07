import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
EXT = REPO / "vlc_extension"


def _free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait(port, path, timeout=20.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}{path}", timeout=1.0)
            return r
        except Exception as e:
            last = e
        time.sleep(0.2)
    raise RuntimeError(f"bridge :{port} never came up: {last}")


@pytest.fixture
def bridge():
    port = _free()
    pf = REPO / f".vlc-bridge-port-{port}"
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(
        [sys.executable, "vlc_discovery_bridge.py",
         "--port", str(port), "--port-file", str(pf), "--host", "127.0.0.1"],
        cwd=str(EXT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        _wait(port, "/v1/health", timeout=20.0)
    except Exception:
        try:
            out, err = p.communicate(timeout=2.0)
        except Exception:
            p.kill()
            out, err = p.communicate()
        raise AssertionError(f"vlc bridge failed.\nstdout={out!r}\nstderr={err!r}")
    yield port
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=3.0)
        except Exception:
            p.kill()
            p.wait(timeout=3.0)
    if pf.exists():
        pf.unlink()


def test_vlc_extension_files_shipped():
    assert EXT.exists()
    assert (EXT / "saturn_chat.lua").exists()
    assert (EXT / "saturn_roast.lua").exists()
    assert (EXT / "vlc_discovery_bridge.py").exists()
    assert (EXT / "README.md").exists()
    assert (EXT / "requirements.txt").exists()


def test_vlc_lua_extensions_reference_bridge_port():
    chat = (EXT / "saturn_chat.lua").read_text()
    roast = (EXT / "saturn_roast.lua").read_text()
    assert "9876" in chat or "127.0.0.1" in chat
    assert "9876" in roast or "127.0.0.1" in roast


def test_vlc_bridge_module_routes_declared():
    src = (EXT / "vlc_discovery_bridge.py").read_text()
    for route in ["/services", "/v1/health", "/v1/models", "/v1/chat/completions", "/shutdown"]:
        assert route in src, f"missing route: {route}"


def test_vlc_bridge_default_port_documented():
    src = (EXT / "vlc_discovery_bridge.py").read_text()
    assert "9876" in src, "default bridge port (9876) must be hard-defaulted in bridge"


def test_vlc_bridge_dns_sd_path():
    src = (EXT / "vlc_discovery_bridge.py").read_text()
    assert "dns-sd" in src
    assert "_saturn._tcp" in src


def test_vlc_bridge_health(bridge):
    r = httpx.get(f"http://127.0.0.1:{bridge}/v1/health", timeout=3.0)
    assert r.status_code == 200, r.text


def test_vlc_bridge_services_endpoint(bridge):
    r = httpx.get(f"http://127.0.0.1:{bridge}/services", timeout=3.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, (list, dict))


def test_vlc_bridge_writes_port_file(bridge):
    end = time.time() + 5.0
    files = []
    while time.time() < end:
        files = list(REPO.glob(".vlc-bridge-port-*"))
        if files:
            break
        time.sleep(0.1)
    assert files, "bridge must write the host:port to --port-file"
    text = files[0].read_text().strip()
    assert ":" in text, f"port file format must be host:port, got {text!r}"


def test_vlc_bridge_shutdown_endpoint(bridge):
    r = httpx.post(f"http://127.0.0.1:{bridge}/shutdown", timeout=3.0)
    assert r.status_code in (200, 202, 204), r.text
