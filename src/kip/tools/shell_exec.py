"""受限异步 Shell 执行。"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from pathlib import Path
from typing import Any

from kip.tools.base import BaseTool

FORBIDDEN_SUBSTR = ("|", ">", ";", "`", "$(", "\n")

_log = logging.getLogger("kip.tools.shell")


def _decode_output(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("gbk")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")


class ShellExecTool(BaseTool):
    name = "shell_exec"
    description = "在固定工作目录执行 shell 命令（无管道、无重定向），超时 30s。"
    is_safe = False

    def __init__(self, cwd: str | Path | None = None) -> None:
        self._cwd = Path(cwd or ".").resolve()

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "单条命令，禁止管道与重定向"},
            },
            "required": ["command"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        cmd = args["command"].strip()
        for bad in FORBIDDEN_SUBSTR:
            if bad in cmd:
                return f"错误: 禁止使用的字符: {bad!r}"
        try:
            parts = shlex.split(cmd, posix=os.name != "nt")
        except ValueError as e:
            return f"错误: 无法解析命令: {e}"
        if not parts:
            return "错误: 空命令"

        # 不继承终端 stdin：避免与 REPL（含 cbreak / Esc 监听）抢同一 TTY，防止子进程结束后输入无响应
        proc = await asyncio.create_subprocess_exec(
            *parts,
            cwd=str(self._cwd),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            return "错误: 命令超时 (30s)"
        text = _decode_output(out)
        code = proc.returncode or 0
        _log.info(
            "shell_exec cwd=%s exit=%s command=%r",
            self._cwd,
            code,
            cmd[:800],
        )
        return f"exit={code}\n{text[:8000]}"
