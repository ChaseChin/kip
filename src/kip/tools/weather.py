"""wttr.in 天气查询。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from kip.tools.base import BaseTool


class WeatherTool(BaseTool):
    name = "get_weather"
    description = "查询城市天气（中文），使用 wttr.in 免费服务。"
    is_safe = True

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "城市名，如 北京"},
            },
            "required": ["location"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        loc = quote(args["location"].strip(), safe="")
        url = f"https://wttr.in/{loc}?lang=zh&format=j1"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
        try:
            cur = data["current_condition"][0]
            area = data["nearest_area"][0]["areaName"][0]["value"]
            desc = cur["weatherDesc"][0]["value"]
            temp = cur["temp_C"]
            return f"{area}: {desc}, {temp}°C"
        except (KeyError, IndexError):
            return r.text[:2000]
