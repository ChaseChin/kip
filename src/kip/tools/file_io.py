"""异步文件读写。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiofiles

from kip.tools.base import BaseTool


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "读取本地文本文件内容（UTF-8）。"
    is_safe = True

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        p = Path(args["path"]).expanduser().resolve()
        if not p.is_file():
            return f"错误: 文件不存在: {p}"
        async with aiofiles.open(p, encoding="utf-8") as f:
            data = await f.read()
        if len(data) > 200_000:
            return data[:200_000] + "\n...(已截断)"
        return data


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "将文本写入本地文件（UTF-8），会覆盖已存在文件。"
    is_safe = False

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "写入内容"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        p = Path(args["path"]).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(p, "w", encoding="utf-8") as f:
            await f.write(args["content"])
        return f"已写入 {p}"
