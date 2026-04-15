"""macOS：通过 osascript 执行 AppleScript。"""

from __future__ import annotations

import asyncio
import platform
import shutil
from pathlib import Path
from typing import Any

from kip.tools.base import BaseTool

_MAX_SCRIPT = 96_000


def _decode_output(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


class AppleScriptTool(BaseTool):
    name = "run_applescript"
    description = (
        "【KIP 内置工具，已随程序加载，无需 install_skill 或单独安装。】"
        "（仅 macOS）使用 osascript 执行 AppleScript，可控制系统与应用"
        "（如 Finder、日历、音乐、提醒事项等）。默认需安全确认。"
    )
    is_safe = False

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "完整 AppleScript 源代码（可多行）",
                },
            },
            "required": ["script"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        if platform.system() != "Darwin":
            return (
                "错误: run_applescript 仅在 macOS 上可用。"
                "（若在 macOS 仍见此条，说明运行环境非 Darwin，例如远程 Linux 容器。）"
            )
        script = str(args.get("script", "")).strip()
        if not script:
            return "错误: script 不能为空"
        if len(script) > _MAX_SCRIPT:
            return f"错误: 脚本长度超过 {_MAX_SCRIPT} 字符"

        osa = shutil.which("osascript")
        if not osa and Path("/usr/bin/osascript").is_file():
            osa = "/usr/bin/osascript"
        if not osa:
            return "错误: 本机未找到 osascript（通常随 macOS 提供）。请检查 PATH 或安装 Xcode 命令行工具。"

        proc = await asyncio.create_subprocess_exec(
            osa,
            "-e",
            script,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            proc.kill()
            return "错误: AppleScript 执行超时 (60s)"
        text = _decode_output(out)
        code = proc.returncode if proc.returncode is not None else -1
        if code != 0:
            return f"osascript 失败 (exit={code})\n{text[:8000]}"
        return text[:8000] if text else "(无输出)"
