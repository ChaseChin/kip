"""示例 skill：回显文本（安装后工具名为 skill_echo__echo_text）。"""

from __future__ import annotations

from typing import Any

from kip.tools.base import BaseTool


class EchoTextTool(BaseTool):
    name = "echo_text"
    description = "将用户提供的文本原样返回，用于测试 skill 是否加载成功。"
    is_safe = True

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要回显的文本"},
            },
            "required": ["text"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        return str(args.get("text", ""))


def build_tools(cwd: str) -> list[BaseTool]:
    _ = cwd
    return [EchoTextTool()]
