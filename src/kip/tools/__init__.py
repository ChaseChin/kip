"""内置工具注册（惰性加载，避免 import 链拉起重依赖）。"""

from __future__ import annotations

from typing import Sequence

from kip.tools.base import BaseTool


def default_tools(cwd: str, browser_hosts: list[str]) -> list[BaseTool]:
    from kip.tools.browser import (
        BrowserClickTool,
        BrowserExtractTool,
        BrowserFillTool,
        BrowserNavigateTool,
        BrowserScreenshotTool,
    )
    from kip.tools.applescript import AppleScriptTool
    from kip.tools.file_io import ReadFileTool, WriteFileTool
    from kip.tools.shell_exec import ShellExecTool
    from kip.tools.weather import WeatherTool

    return [
        ReadFileTool(),
        WriteFileTool(),
        ShellExecTool(cwd=cwd),
        AppleScriptTool(),
        WeatherTool(),
        BrowserNavigateTool(browser_hosts),
        BrowserScreenshotTool(browser_hosts),
        BrowserExtractTool(browser_hosts),
        BrowserClickTool(browser_hosts),
        BrowserFillTool(browser_hosts),
    ]


def tools_by_name(tools: Sequence[BaseTool]) -> dict[str, BaseTool]:
    return {t.name: t for t in tools}
