import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

CALL_DEADLINE_S = 5.0

logger = logging.getLogger("saturn.mcp_client")

CONFIG_PATH = Path.home() / ".saturn" / "mcp-servers.json"


def _load() -> list[dict]:
    if not CONFIG_PATH.exists():
        return []
    return json.loads(CONFIG_PATH.read_text())


def _save(servers: list[dict]):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(servers, indent=2) + "\n")


def _unwrap(exc: BaseException) -> BaseException:
    seen = set()
    cur = exc
    while isinstance(cur, BaseExceptionGroup) and id(cur) not in seen:
        seen.add(id(cur))
        if not cur.exceptions:
            break
        cur = cur.exceptions[0]
    return cur


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
            return {"error": f"Server '{server}' not configured"}
        try:
            async def invoke(session):
                result = await session.call_tool(tool, arguments)
                return {"content": [c.model_dump() for c in result.content], "isError": result.isError}
            return await asyncio.wait_for(
                _with_session(entry["url"], entry.get("auth_token"), invoke),
                timeout=CALL_DEADLINE_S,
            )
        except asyncio.TimeoutError:
            return {"error": f"MCP tool {tool!r} on {server!r} timed out after {CALL_DEADLINE_S}s deadline"}
        except BaseException as e:
            inner = _unwrap(e)
            if isinstance(inner, asyncio.TimeoutError):
                return {"error": f"MCP tool {tool!r} on {server!r} timed out after {CALL_DEADLINE_S}s deadline"}
            if isinstance(inner, (ConnectionError, OSError)):
                return {"error": f"MCP server '{server}' unreachable at {entry['url']}: {inner}"}
            return {"error": f"MCP server '{server}' at {entry['url']} failed: {inner}"}

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
