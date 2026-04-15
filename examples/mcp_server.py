#!/usr/bin/env python3
"""示例 MCP Server：提供 echo 工具（stdio）。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kip-demo")


@mcp.tool()
def echo(text: str) -> str:
    """回显输入文本。"""
    return f"echo: {text}"


if __name__ == "__main__":
    mcp.run()
