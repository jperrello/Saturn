import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
import pytest


REPO = Path(__file__).resolve().parents[2]


# ---- Surface A: saturn-mcp package (Saturn → MCP host over stdio) ----

def test_mcp_package_shipped():
    pkg = REPO / "saturn-mcp"
    assert pkg.exists()
    pyproject = pkg / "pyproject.toml"
    assert pyproject.exists()
    assert "saturn-mcp" in pyproject.read_text()


def test_mcp_server_module_importable():
    sys.path.insert(0, str(REPO / "saturn-mcp"))
    try:
        import importlib
        if "saturn_mcp.server" in sys.modules:
            del sys.modules["saturn_mcp.server"]
        mod = importlib.import_module("saturn_mcp.server")
        assert hasattr(mod, "mcp")
        assert hasattr(mod, "main")
    finally:
        sys.path.pop(0)


def test_mcp_server_registers_documented_tools():
    sys.path.insert(0, str(REPO / "saturn-mcp"))
    try:
        import importlib
        if "saturn_mcp.server" in sys.modules:
            del sys.modules["saturn_mcp.server"]
        mod = importlib.import_module("saturn_mcp.server")
        names = asyncio.run(mod.mcp.list_tools())
        ids = {t.name for t in names}
        assert "discover_saturn_services" in ids
        assert "list_available_models" in ids
        assert "find_service_for_model" in ids
    finally:
        sys.path.pop(0)


def test_mcp_server_entrypoint_declared():
    txt = (REPO / "saturn-mcp" / "pyproject.toml").read_text()
    assert "saturn-mcp = " in txt
    assert "saturn_mcp.server:main" in txt


# ---- Surface B: saturn/mcp_client.py (Saturn web UI → remote MCP servers) ----

def test_mcp_client_module_importable():
    import importlib
    mod = importlib.import_module("saturn.mcp_client")
    assert hasattr(mod, "MCPClientManager")
    assert hasattr(mod, "_classify")
    assert hasattr(mod, "_flatten")


def test_mcp_client_env_knobs_documented():
    import importlib
    mod = importlib.import_module("saturn.mcp_client")
    assert mod.CALL_DEADLINE_S == 30.0
    assert mod.LARGE_RESULT_BYTES == 1024 * 1024
    assert mod.RESULT_CACHE_TTL_S == 600.0


def test_mcp_client_env_overrides(monkeypatch):
    monkeypatch.setenv("SATURN_MCP_TOOL_TIMEOUT_SEC", "7.5")
    monkeypatch.setenv("SATURN_MCP_MAX_RESULT_BYTES", "2048")
    monkeypatch.setenv("SATURN_MCP_RESULT_TTL_SEC", "120")
    import importlib
    if "saturn.mcp_client" in sys.modules:
        del sys.modules["saturn.mcp_client"]
    mod = importlib.import_module("saturn.mcp_client")
    assert mod.CALL_DEADLINE_S == 7.5
    assert mod.LARGE_RESULT_BYTES == 2048
    assert mod.RESULT_CACHE_TTL_S == 120.0


def test_mcp_client_config_path_in_dot_saturn():
    import importlib
    if "saturn.mcp_client" in sys.modules:
        del sys.modules["saturn.mcp_client"]
    mod = importlib.import_module("saturn.mcp_client")
    assert mod.CONFIG_PATH == Path.home() / ".saturn" / "mcp-servers.json"


def test_mcp_client_classify_unreachable():
    import importlib
    if "saturn.mcp_client" in sys.modules:
        del sys.modules["saturn.mcp_client"]
    mod = importlib.import_module("saturn.mcp_client")
    assert mod._classify(httpx.ConnectError("boom")) == "unreachable"
    assert mod._classify(asyncio.TimeoutError()) == "timeout"
    assert mod._classify(RuntimeError("unrelated")) == "internal"


def test_mcp_client_classify_walks_exception_group():
    import importlib
    if "saturn.mcp_client" in sys.modules:
        del sys.modules["saturn.mcp_client"]
    mod = importlib.import_module("saturn.mcp_client")
    eg = BaseExceptionGroup("g", [RuntimeError("x"), httpx.ConnectError("y")])
    assert mod._classify(eg) == "unreachable"


def test_mcp_client_persistence_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    import importlib
    if "saturn.mcp_client" in sys.modules:
        del sys.modules["saturn.mcp_client"]
    mod = importlib.import_module("saturn.mcp_client")
    assert mod.CONFIG_PATH == tmp_path / ".saturn" / "mcp-servers.json"
    mod._save([{"name": "test", "url": "https://example/mcp"}])
    assert mod.CONFIG_PATH.exists()
    loaded = mod._load()
    assert loaded == [{"name": "test", "url": "https://example/mcp"}]
