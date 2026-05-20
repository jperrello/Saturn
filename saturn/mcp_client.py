import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup


# Saturn-cbt.2.3: knobs are env-driven so deployments can tune without
# editing code. Defaults match the bead spec: 30s tool deadline, 1 MB
# inline-result ceiling above which the payload is truncated and offered
# via a download URL instead.
def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


CALL_DEADLINE_S = _env_float("SATURN_MCP_TOOL_TIMEOUT_SEC", 30.0)
LARGE_RESULT_BYTES = _env_int("SATURN_MCP_MAX_RESULT_BYTES", 1024 * 1024)
RESULT_CACHE_TTL_S = _env_float("SATURN_MCP_RESULT_TTL_SEC", 600.0)

logger = logging.getLogger("saturn.mcp_client")

CONFIG_PATH = Path.home() / ".saturn" / "mcp-servers.json"


def _load() -> list[dict]:
    if not CONFIG_PATH.exists():
        return []
    return json.loads(CONFIG_PATH.read_text())


def _save(servers: list[dict]):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(servers, indent=2) + "\n")


_UNREACHABLE_TYPES = (httpx.NetworkError, httpx.ConnectError, httpx.ConnectTimeout,
                      ConnectionError, OSError)
_TIMEOUT_TYPES = (asyncio.TimeoutError, httpx.ReadTimeout, httpx.PoolTimeout)


def _flatten(exc: BaseException) -> list[BaseException]:
    out: list[BaseException] = []
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, BaseExceptionGroup):
            stack.extend(cur.exceptions)
            continue
        out.append(cur)
        if cur.__cause__ is not None:
            stack.append(cur.__cause__)
        if cur.__context__ is not None:
            stack.append(cur.__context__)
    return out


def _classify(exc: BaseException) -> str:
    flat = _flatten(exc)
    if any(isinstance(e, _TIMEOUT_TYPES) for e in flat):
        return "timeout"
    if any(isinstance(e, _UNREACHABLE_TYPES) for e in flat):
        return "unreachable"
    return "internal"


def _unwrap(exc: BaseException) -> BaseException:
    flat = _flatten(exc)
    for e in flat:
        if isinstance(e, _UNREACHABLE_TYPES + _TIMEOUT_TYPES):
            return e
    return flat[0] if flat else exc


async def _with_session(url: str, auth_token: Optional[str], fn):
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    async with streamablehttp_client(url, headers=headers or None) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


class MCPClientManager:
    def __init__(self):
        self._tools_cache: dict[str, list[dict]] = {}
        # Result cache for oversized MCP tool results. Keyed by random id;
        # value is (epoch_expires, full_content). GC on every read/write.
        self._results: dict[str, tuple[float, list[dict]]] = {}

    def _gc_results(self):
        now = time.monotonic()
        stale = [rid for rid, (exp, _) in self._results.items() if exp <= now]
        for rid in stale:
            self._results.pop(rid, None)

    def get_result(self, rid: str) -> Optional[list[dict]]:
        self._gc_results()
        entry = self._results.get(rid)
        if not entry:
            return None
        return entry[1]

    def configured(self) -> list[dict]:
        return _load()

    async def refresh(self, name: str):
        servers = _load()
        server = next((s for s in servers if s["name"] == name), None)
        if not server:
            return
        try:
            async def fetch(session):
                result = await session.list_tools()
                return [
                    {"name": t.name, "description": t.description or "", "schema": t.inputSchema or {}}
                    for t in result.tools
                ]
            self._tools_cache[name] = await _with_session(
                server["url"], server.get("auth_token"), fetch
            )
        except Exception as e:
            logger.warning(f"Failed to refresh tools from {name}: {e}")
            self._tools_cache.pop(name, None)
            raise

    def tools(self) -> list[dict]:
        result = []
        for server, items in self._tools_cache.items():
            for t in items:
                result.append({**t, "server": server})
        return result

    async def call(self, server: str, tool: str, arguments: dict) -> dict:
        servers = _load()
        entry = next((s for s in servers if s["name"] == server), None)
        if not entry:
            return {"errorKind": "config", "error": f"MCP server unreachable: {server}",
                    "tool": tool, "server": server}
        try:
            async def invoke(session):
                result = await session.call_tool(tool, arguments)
                content = [c.model_dump() for c in result.content]
                total = sum(len(str(c.get("text", ""))) for c in content if isinstance(c, dict))
                if total > LARGE_RESULT_BYTES:
                    rid = uuid.uuid4().hex
                    self._gc_results()
                    self._results[rid] = (time.monotonic() + RESULT_CACHE_TTL_S, content)
                    truncated = self._truncate_content(content, LARGE_RESULT_BYTES)
                    return {
                        "content": truncated,
                        "isError": result.isError,
                        "truncated": {
                            "full_bytes": total,
                            "kept_bytes": LARGE_RESULT_BYTES,
                            "result_id": rid,
                            "download_url": f"/api/mcp/result/{rid}",
                        },
                    }
                return {"content": content, "isError": result.isError}
            return await asyncio.wait_for(
                _with_session(entry["url"], entry.get("auth_token"), invoke),
                timeout=CALL_DEADLINE_S,
            )
        except BaseException as e:
            kind = _classify(e)
            inner = _unwrap(e)
            if kind == "timeout":
                return {"errorKind": "timeout", "tool": tool, "server": server,
                        "deadline_s": CALL_DEADLINE_S,
                        "error": f"Tool call timed out: {tool}"}
            if kind == "unreachable":
                return {"errorKind": "unreachable", "tool": tool, "server": server,
                        "url": entry["url"], "detail": str(inner),
                        "error": f"MCP server unreachable: {server}"}
            return {"errorKind": "internal", "tool": tool, "server": server,
                    "url": entry["url"], "detail": str(inner),
                    "error": f"MCP tool failed: {tool} ({inner})"}

    @staticmethod
    def _truncate_content(content: list[dict], cap: int) -> list[dict]:
        out = []
        remaining = cap
        for c in content:
            if not isinstance(c, dict):
                out.append(c)
                continue
            text = c.get("text")
            if not isinstance(text, str):
                out.append(c)
                continue
            if remaining <= 0:
                continue
            if len(text) <= remaining:
                out.append(c)
                remaining -= len(text)
                continue
            kept = text[:remaining]
            out.append({**c, "text": kept + "\n\n[... result truncated; download full via the badge link ...]"})
            remaining = 0
        return out

    def add(self, name: str, url: str, auth_token: Optional[str] = None):
        servers = _load()
        for s in servers:
            if s["name"] == name:
                return
        entry = {"name": name, "url": url}
        if auth_token:
            entry["auth_token"] = auth_token
        servers.append(entry)
        _save(servers)

    def remove(self, name: str) -> bool:
        servers = _load()
        filtered = [s for s in servers if s["name"] != name]
        if len(filtered) == len(servers):
            return False
        _save(filtered)
        self._tools_cache.pop(name, None)
        return True


manager = MCPClientManager()
