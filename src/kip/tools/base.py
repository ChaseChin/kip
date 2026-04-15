"""工具基类与 OpenAI 工具格式转换。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str
    description: str
    is_safe: bool = True

    @property
    @abstractmethod
    def schema(self) -> dict[str, Any]:
        ...

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> str:
        ...

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            },
        }
