"""Rich 步骤与事件输出。"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from kip.branding import assistant_reply_panel

# LLM 等待时轮换提示：6 个汉字 +「...」；计时为 (0.0s)
THINKING_HINTS_FIRST: list[str] = [
    "正在分析意图...",
    "正在调用模型...",
    "正在推理当中...",
    "正在生成回复...",
    "正在等待结果...",
]

THINKING_HINTS_FOLLOWUP: list[str] = [
    "正在整合工具...",
    "正在汇总输出...",
    "正在生成答复...",
    "正在二次推理...",
    "即将完成处理...",
    "正在等待完成...",
]

# 长期记忆提取（额外一次 LLM，无提示时易误以为卡住）
THINKING_HINTS_MEMORY: list[str] = [
    "正在提炼记忆...",
    "正在归档要点...",
    "正在写入记忆...",
]

# 启动 /loaddev：从 DEV.MD 提炼到全局记忆
THINKING_HINTS_DEV_MD: list[str] = [
    "正在读取文档...",
    "正在提炼要点...",
    "正在写入记忆...",
]


class StepEmitter:
    """统一步骤输出，避免业务层直接 print。"""

    def __init__(
        self, console: Console | None = None, *, trace_tools: bool = False
    ) -> None:
        self._console = console or Console(highlight=False)
        self._step = 0
        self._trace_tools = trace_tools

    @property
    def console(self) -> Console:
        return self._console

    def reset_step(self) -> None:
        self._step = 0

    def step_start(self, desc: str) -> int:
        if not self._trace_tools:
            return self._step
        self._step += 1
        self._console.print(f"[dim]📝 步骤 {self._step}:[/dim] {desc}")
        return self._step

    def step_ok(self, summary: str) -> None:
        if not self._trace_tools:
            return
        self._console.print(f"[green]✅ 完成:[/green] {summary}")

    def step_fail(self, err: str) -> None:
        # 非 trace 时也输出失败，避免工具错误被完全静默
        self._console.print(f"[red]❌ 失败:[/red] {err}")

    def info(self, msg: str) -> None:
        self._console.print(msg)

    def markdown_reply(
        self,
        text: str,
        *,
        elapsed_s: float | None = None,
        turn_tokens: int | None = None,
        session_tokens: int | None = None,
    ) -> None:
        self._console.print(assistant_reply_panel(text))
        if (
            elapsed_s is not None
            and turn_tokens is not None
            and session_tokens is not None
        ):
            self._console.print(
                "[dim]"
                f"⚡ 耗时: {elapsed_s:.2f}s | "
                f"🪙 本次消耗: {turn_tokens} tokens | "
                f"累计: {session_tokens} tokens"
                "[/dim]"
            )

    def tool_line(self, name: str, args_preview: str) -> None:
        if not self._trace_tools:
            return
        self._console.print(f"[cyan]🔧 {name}[/cyan] [dim]{args_preview}[/dim]")

    @asynccontextmanager
    async def thinking(self, hints: list[str] | None = None) -> AsyncIterator[None]:
        """在 await LLM 期间显示旋转 spinner + 轮换文案 + 已用秒数，结束后自动清除。"""
        msgs = hints or THINKING_HINTS_FIRST
        idx = [0]
        t0 = time.monotonic()

        # 必须复用同一 Spinner 实例，否则每次 Live.update 新建会重置动画帧，圆点不转
        spinner = Spinner("dots", style="cyan", text="")

        def refresh_spinner_text() -> None:
            elapsed = time.monotonic() - t0
            hint = msgs[idx[0] % len(msgs)]
            spinner.text = Text.assemble(
                " ",
                hint,
                " ",
                Text(f"({elapsed:.1f}s)", style="dim"),
            )

        refresh_spinner_text()

        live = Live(
            spinner,
            console=self._console,
            refresh_per_second=12,
            transient=True,
        )
        live.start()

        async def _rotate() -> None:
            """约每 0.1s 刷新计时；约每 0.5s 轮换一条提示词。"""
            try:
                tick = 0
                while True:
                    await asyncio.sleep(0.1)
                    tick += 1
                    if tick % 5 == 0:
                        idx[0] += 1
                    refresh_spinner_text()
                    live.update(spinner)
            except asyncio.CancelledError:
                raise

        task = asyncio.create_task(_rotate())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            live.stop()


def format_tool_args_preview(args: dict[str, Any], max_len: int = 200) -> str:
    import json

    try:
        s = json.dumps(args, ensure_ascii=False)
    except Exception:
        s = str(args)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s
