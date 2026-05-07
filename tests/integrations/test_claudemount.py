import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path("/tmp/claude-fixture")
FIXTURE_BODY = "FIXTURE-CONTENTS-7im\n"


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait_http(port, path="/", timeout=10.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}{path}", timeout=1.0)
            return r
        except Exception as e:
            last = e
            time.sleep(0.2)
    raise RuntimeError(f"server on :{port} never came up: {last}")


def _spawn(args, port):
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(
        [sys.executable, "-m", "saturn"] + args + ["--host", "127.0.0.1", "--port", str(port)],
        cwd=str(REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_http(port, "/", timeout=15.0)
    except Exception:
        try:
            out, err = p.communicate(timeout=2.0)
        except Exception:
            p.kill()
            out, err = p.communicate()
        raise AssertionError(
            f"saturn serve failed to start (behavior missing).\n"
            f"args={args}\nstdout={out!r}\nstderr={err!r}"
        )
    return p


def _kill(p):
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=3.0)
        except Exception:
            p.kill()
            p.wait(timeout=3.0)


def _browse_txt(timeout=4.0):
    from zeroconf import Zeroconf, ServiceBrowser
    found = {}

    class L:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name, timeout=2000)
            if info:
                txt = {k.decode(): (v.decode() if isinstance(v, bytes) else v)
                       for k, v in (info.properties or {}).items()}
                found[name] = (info.port, txt)
        def update_service(self, *a, **k): pass
        def remove_service(self, *a, **k): pass

    zc = Zeroconf()
    try:
        ServiceBrowser(zc, "_saturn._tcp.local.", L())
        time.sleep(timeout)
        return dict(found)
    finally:
        zc.close()


@pytest.fixture
def fixture_dir():
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    FIXTURE.mkdir(parents=True)
    (FIXTURE / "CLAUDE.md").write_text(FIXTURE_BODY)
    (FIXTURE / "sub").mkdir()
    (FIXTURE / "sub" / "note.txt").write_text("nested\n")
    yield FIXTURE
    shutil.rmtree(FIXTURE, ignore_errors=True)


def _snapshot(root):
    out = {}
    for p in root.rglob("*"):
        if p.is_file():
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


# Invariant 1 — default: no kind=claude, no /share/claude/
def test_default_no_share():
    port = _free_port()
    p = _spawn(["serve"], port)
    try:
        services = _browse_txt(timeout=4.0)
        ours = [(n, t) for n, (po, t) in services.items() if po == port]
        assert ours, f"saturn serve did not advertise on :{port} (browsed: {list(services)})"
        for _, txt in ours:
            assert txt.get("kind") != "claude", f"default run leaked kind=claude: {txt}"
        r = httpx.get(f"http://127.0.0.1:{port}/share/claude/", timeout=2.0)
        assert r.status_code == 404, f"default run exposed /share/claude/ (status {r.status_code})"
    finally:
        _kill(p)


# Invariant 2 — opt-in: kind=claude, GET 200, PROPFIND 207
def test_optin_share_claude(fixture_dir):
    port = _free_port()
    p = _spawn(["serve", "--share-claude", "--share-claude-path", str(fixture_dir)], port)
    try:
        services = _browse_txt(timeout=4.0)
        ours = [t for n, (po, t) in services.items() if po == port]
        assert any(t.get("kind") == "claude" for t in ours), f"no kind=claude in TXT: {ours}"

        r = httpx.get(f"http://127.0.0.1:{port}/share/claude/CLAUDE.md", timeout=3.0)
        assert r.status_code == 200, f"GET /share/claude/CLAUDE.md -> {r.status_code}"
        assert FIXTURE_BODY in r.text, f"body mismatch: {r.text!r}"

        r = httpx.request(
            "PROPFIND",
            f"http://127.0.0.1:{port}/share/claude/",
            headers={"Depth": "1", "Content-Type": "application/xml"},
            content=b'<?xml version="1.0"?><propfind xmlns="DAV:"><allprop/></propfind>',
            timeout=3.0,
        )
        assert r.status_code == 207, f"PROPFIND -> {r.status_code}, body={r.text[:300]!r}"
        assert "multistatus" in r.text.lower()
    finally:
        _kill(p)


# Invariant 3 — RO matrix: PUT/DELETE/MKCOL/MOVE/COPY/PROPPATCH all 403, FS unchanged
@pytest.mark.parametrize(
    "method,target,headers,body",
    [
        ("PUT", "newfile.txt", {}, b"x"),
        ("DELETE", "CLAUDE.md", {}, b""),
        ("MKCOL", "newdir/", {}, b""),
        ("MOVE", "CLAUDE.md", {"Destination": "/share/claude/moved.md"}, b""),
        ("COPY", "CLAUDE.md", {"Destination": "/share/claude/copy.md"}, b""),
        ("PROPPATCH", "CLAUDE.md",
         {"Content-Type": "application/xml"},
         b'<?xml version="1.0"?><propertyupdate xmlns="DAV:"><set><prop><z xmlns="z:">v</z></prop></set></propertyupdate>'),
    ],
)
def test_ro_enforcement(fixture_dir, method, target, headers, body):
    port = _free_port()
    before = _snapshot(fixture_dir)
    p = _spawn(["serve", "--share-claude", "--share-claude-path", str(fixture_dir)], port)
    try:
        r = httpx.request(
            method,
            f"http://127.0.0.1:{port}/share/claude/{target}",
            headers=headers,
            content=body,
            timeout=3.0,
        )
        assert r.status_code == 403, f"{method} {target} -> {r.status_code}, expected 403"
    finally:
        _kill(p)
    assert _snapshot(fixture_dir) == before, f"{method} mutated the share root"


# Invariant 4 — discovery surfaces kind, openai consumers ignore claude cleanly
def test_discovery_filters_kind(fixture_dir):
    port = _free_port()
    p = _spawn(["serve", "--share-claude", "--share-claude-path", str(fixture_dir)], port)
    try:
        from saturn.discovery import discover
        services = discover(timeout=5.0)
        mine = [s for s in services if s.port == port]
        assert mine, f"discover() did not return our service on :{port}"
        kinds = [getattr(s, "kind", None) for s in mine]
        assert "claude" in kinds, f"no kind=claude on discovered service: {kinds}"
        openai_only = [s for s in services if getattr(s, "kind", "openai") == "openai"]
        assert all(getattr(s, "kind", "openai") != "claude" for s in openai_only), \
            "openai filter leaked a claude service"
    finally:
        _kill(p)


# Invariant 5 — path traversal contained
@pytest.mark.parametrize("evil", [
    "../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "%2e%2e/%2e%2e/etc/passwd",
])
def test_path_traversal_blocked(fixture_dir, evil):
    port = _free_port()
    p = _spawn(["serve", "--share-claude", "--share-claude-path", str(fixture_dir)], port)
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/share/claude/{evil}", timeout=3.0)
        assert r.status_code in (403, 404), f"traversal {evil!r} -> {r.status_code}"
        assert "root:" not in r.text, "leaked /etc/passwd contents"
    finally:
        _kill(p)
