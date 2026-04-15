"""安全门控：预览、确认、YOLO 模式。"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from typing import Awaitable, Callable, Union

ConfirmFn = Callable[[str], Union[bool, Awaitable[bool]]]


def _stdin_cooked_hint() -> None:
    """在部分终端里，prompt_toolkit 结束后仍可能处于 raw/cbreak；随后 ``input()`` 会读不到行。

    对交互式 TTY 尝试恢复常见行规（忽略失败）。"""
    if not sys.stdin.isatty():
        return
    if sys.platform == "win32":
        return
    # 子 shell 作用于当前控制终端；失败时静默
    if os.environ.get("KIP_SKIP_STTY_SANE", "").strip() not in ("", "0", "false"):
        return
    os.system("stty sane 2>/dev/null")


def _flush_stdin_if_tty() -> None:
    """丢弃 stdin 中可能残留的按键/换行，避免下一轮 ``prompt_async`` 挂起或误读。"""
    if not sys.stdin.isatty():
        return
    try:
        import termios

        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:
        pass


async def prompt_one_line(message: str) -> str:
    """工具确认、/setup 等单行提示：在线程池中 ``input()``，不阻塞 asyncio 事件循环。

    若在 ``async`` 里直接 ``input()``，会占死事件循环，可能导致确认后主界面 ``prompt_async`` 无法继续。
    与主 REPL 的 prompt_toolkit 仍分离（确认不用 PT）。"""
    _stdin_cooked_hint()
    try:
        line = await asyncio.to_thread(input, message)
    except EOFError:
        return ""
    _flush_stdin_if_tty()
    return line


class SafetyGate:
    """非只读操作需确认；YOLO 可跳过（删除类操作仍可强制确认）。"""

    def __init__(
        self,
        *,
        yolo: bool = False,
        enabled: bool = True,
        confirm_fn: ConfirmFn | None = None,
    ) -> None:
        self.yolo = yolo
        self.enabled = enabled
        self._confirm_fn = confirm_fn

    def set_yolo(self, value: bool) -> None:
        self.yolo = value

    def set_enabled(self, value: bool) -> None:
        self.enabled = value

    def is_destructive(self, description: str) -> bool:
        low = description.lower()
        keys = ("delete", "rm ", "remove", "unlink", "truncate", "drop ")
        return any(k in low for k in keys)

    async def confirm(self, action_desc: str) -> bool:
        if not self.enabled:
            return True
        if self.yolo and not self.is_destructive(action_desc):
            return True
        if self._confirm_fn:
            result = self._confirm_fn(action_desc)
            if inspect.isawaitable(result):
                return await result  # type: ignore[no-any-return]
            return bool(result)
        text = await prompt_one_line(f"[安全确认] {action_desc}\n执行? [y/N]: ")
        t = text.strip().lower()
        return t == "y" or t == "yes"
