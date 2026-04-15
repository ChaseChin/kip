"""安全门控：预览、确认、YOLO 模式。"""

from __future__ import annotations

import asyncio
import inspect
from typing import Awaitable, Callable, Union

ConfirmFn = Callable[[str], Union[bool, Awaitable[bool]]]


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
        # 默认终端确认
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: input(f"[安全确认] {action_desc}\n执行? [y/N]: ").strip().lower() == "y",
        )
