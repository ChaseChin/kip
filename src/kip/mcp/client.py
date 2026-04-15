"""MCP stdio 客户端：发现工具并包装为 BaseTool。"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Sequence

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from kip.tools.base import BaseTool


def _safe_name(server: str, tool: str) -> str:
    raw = f"mcp_{server}_{tool}"
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)


class _MCPProxyTool(BaseTool):
    """单个 MCP 工具代理（每次执行建立短连接）。"""

    def __init__(
        self,
        *,
        server_label: str,
        tool_name: str,
        description: str,
        input_schema: dict[str, Any],
        command: str,
        args: list[str],
        env: dict[str, str] | None,
    ) -> None:
        self._server_label = server_label
        self._tool_name = tool_name
        self._desc = description
        self._schema = input_schema
        self._command = command
        self._args = args
        self._env = env
        self.name = _safe_name(server_label, tool_name)
        self.description = f"[MCP:{server_label}] {description}"
        self.is_safe = False

    @property
    def schema(self) -> dict[str, Any]:
        if self._schema and self._schema.get("type"):
            return self._schema
        return {"type": "object", "properties": {}, "additionalProperties": True}

    async def execute(self, args: dict[str, Any]) -> str:
        params = StdioServerParameters(command=self._command, args=self._args, env=self._env)

        async def _call() -> str:
            async with stdio_client(params) as streams:
                read, write = streams
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(self._tool_name, arguments=args)
                    parts: list[str] = []
                    for c in result.content:
                        if hasattr(c, "text") and c.text:
                            parts.append(c.text)
                        elif isinstance(c, dict) and c.get("text"):
                            parts.append(str(c["text"]))
                    return "\n".join(parts) if parts else json.dumps(
                        result.model_dump() if hasattr(result, "model_dump") else str(result),
                        ensure_ascii=False,
                    )

        return await asyncio.wait_for(_call(), timeout=120.0)


async def discover_stdio_tools(
    server_label: str,
    command: str,
    args: list[str],
    env: dict[str, str] | None = None,
) -> list[BaseTool]:
    """连接 MCP server 并列出工具，生成代理 BaseTool 列表。"""
    params = StdioServerParameters(command=command, args=args, env=env)
    out: list[BaseTool] = []

    async with stdio_client(params) as streams:
        read, write = streams
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            for t in listed.tools:
                td = t.model_dump() if hasattr(t, "model_dump") else {}
                name = str(td.get("name") or getattr(t, "name", "tool"))
                desc = str(td.get("description") or getattr(t, "description", "") or name)
                schema = td.get("inputSchema") or td.get("input_schema") or {}
                if not isinstance(schema, dict):
                    schema = {}
                out.append(
                    _MCPProxyTool(
                        server_label=server_label,
                        tool_name=name,
                        description=desc,
                        input_schema=schema,
                        command=command,
                        args=args,
                        env=env,
                    )
                )
    return out


def merge_tools(base: Sequence[BaseTool], mcp_tools: Sequence[BaseTool]) -> list[BaseTool]:
    """合并内置与 MCP 工具（同名时 MCP 覆盖）。"""
    by_name: dict[str, BaseTool] = {t.name: t for t in base}
    for t in mcp_tools:
        by_name[t.name] = t
    return list(by_name.values())
