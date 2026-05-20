import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _run(args, timeout=30.0):
    return subprocess.run(
        [sys.executable, "-m", "saturn"] + args,
        cwd=str(REPO), capture_output=True, text=True, timeout=timeout,
    )


# Invariant 1 — `saturn cursor-snippet` is a real subcommand
def test_cursor_subcommand_exists():
    r = _run(["cursor-snippet", "--help"], timeout=10.0)
    assert r.returncode == 0, (
        f"`saturn cursor-snippet --help` exited {r.returncode}.\n"
        f"stderr={r.stderr!r}"
    )
    blob = (r.stdout + r.stderr).lower()
    assert "cursor" in blob, f"help output must mention Cursor: {blob!r}"


# Invariant 2 — explicit --base-url override is rendered into the snippet verbatim
def test_cursor_snippet_renders_base_url():
    r = _run(["cursor-snippet", "--base-url", "http://saturn.local:8080/v1"], timeout=10.0)
    assert r.returncode == 0, f"exit={r.returncode} stderr={r.stderr!r}"
    assert "http://saturn.local:8080/v1" in r.stdout, \
        f"snippet must echo --base-url verbatim. stdout={r.stdout!r}"


# Invariant 3 — snippet warns about Cursor Agent mode breakage and steers to Ask mode
def test_cursor_snippet_warns_ask_mode():
    r = _run(["cursor-snippet", "--base-url", "http://x:1/v1"], timeout=10.0)
    assert r.returncode == 0
    blob = r.stdout.lower()
    assert "ask mode" in blob or "ask-mode" in blob, \
        f"snippet must steer to Ask mode (Cursor Agent mode breaks on custom OpenAI). stdout={r.stdout!r}"
    assert "agent" in blob, "snippet must mention Agent mode limitation"


# Invariant 4 — snippet warns about HTTP/2 incompatibility, instructs HTTP/1.1
def test_cursor_snippet_warns_http2():
    r = _run(["cursor-snippet", "--base-url", "http://x:1/v1"], timeout=10.0)
    assert r.returncode == 0
    blob = r.stdout.lower()
    assert "http/1.1" in blob or "http 1.1" in blob, \
        f"snippet must instruct HTTP/1.1 compatibility mode. stdout={r.stdout!r}"
    assert "http/2" in blob or "http 2" in blob, \
        f"snippet must reference HTTP/2 incompatibility. stdout={r.stdout!r}"


# Invariant 5 — snippet walks the GUI flow (Settings > Models, "Override OpenAI Base URL")
def test_cursor_snippet_describes_gui_flow():
    r = _run(["cursor-snippet", "--base-url", "http://x:1/v1"], timeout=10.0)
    assert r.returncode == 0
    blob = r.stdout.lower()
    assert "settings" in blob and "models" in blob, \
        f"snippet must reference 'Settings > Models' GUI path. stdout={r.stdout!r}"
    assert "override" in blob and "base url" in blob, \
        f"snippet must reference the 'Override OpenAI Base URL' toggle. stdout={r.stdout!r}"


# Invariant 6 — snippet warns that subagents bypass the override (forum source #6)
def test_cursor_snippet_warns_subagents():
    r = _run(["cursor-snippet", "--base-url", "http://x:1/v1"], timeout=10.0)
    assert r.returncode == 0
    assert "subagent" in r.stdout.lower(), \
        f"snippet must warn subagents bypass the override. stdout={r.stdout!r}"


# Invariant 7 — without --base-url, snippet attempts discovery and prints either the
# discovered endpoint or a clear "no Saturn service found" hint.
def test_cursor_snippet_discovers_real_service():
    from saturn.discovery import SaturnAdvertiser
    port = _free_port()
    adv = SaturnAdvertiser(
        name=f"saturn-cursor-test-{port}",
        port=port,
        deployment="network",
        api_type="openai",
        api_base=f"http://127.0.0.1:{port}/v1",
        priority=10,
    )
    adv.register()
    time.sleep(1.0)
    try:
        r = _run(["cursor-snippet", "--timeout", "4"], timeout=20.0)
        assert r.returncode == 0, f"exit={r.returncode} stderr={r.stderr!r}"
        assert f":{port}/v1" in r.stdout, \
            f"snippet must surface discovered endpoint :{port}/v1. stdout={r.stdout!r}"
    finally:
        adv.unregister()


# Invariant 8 — saturn.clients.cursor is importable
def test_cursor_client_module_importable():
    import importlib
    mod = importlib.import_module("saturn.clients.cursor")
    assert mod is not None


# Invariant 9 — docs/integrations/cursor.md exists and covers the constraints
def test_cursor_doc_exists():
    p = REPO / "docs" / "integrations" / "cursor.md"
    assert p.exists(), f"missing {p}"
    blob = p.read_text().lower()
    for kw in ("ask mode", "http/1.1", "settings", "override", "subagent"):
        assert kw in blob, f"docs/integrations/cursor.md must cover {kw!r}"
