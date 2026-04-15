"""退出 REPL 时展示会话摘要（不用 Markdown 表格，避免 Rich 按终端宽度撑开 Panel）。"""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from kip.memory import MemoryStore
from kip.repl_common import UsageTracker


def _exit_summary_group(
    *,
    elapsed_s: float,
    usage: UsageTracker,
    stats: dict[str, int],
) -> Group:
    return Group(
        Text("本次会话摘要", style="bold"),
        Text(""),
        Text.from_markup(f"运行时间：[cyan]{elapsed_s:.1f}[/] 秒"),
        Text.from_markup(
            "Token 消耗（估算）："
            f"[bold]{usage.session_total}[/] total · "
            f"prompt [bold]{usage.prompt}[/] · "
            f"completion [bold]{usage.completion}[/]"
        ),
        Text(""),
        Text("记忆与数据", style="bold"),
        Text(f"  本会话消息（已落库）：{stats['messages_session']} 条"),
        Text(f"  本会话工具调用记录：{stats['tool_logs_session']} 条"),
        Text(f"  长期记忆（全局）：{stats['memories_long_global']} 条"),
        Text(f"  会话级记忆条目：{stats['memories_session_scoped']} 条"),
        Text(f"  记忆表总行数：{stats['memories_total']} 条"),
        Text(""),
        Text(
            "数据已写入本地 SQLite，下次启动可继续会话。",
            style="dim italic",
        ),
    )


async def print_exit_summary(
    console: Console,
    *,
    elapsed_s: float,
    usage: UsageTracker,
    mem: MemoryStore,
    session_id: str,
) -> None:
    stats = await mem.get_exit_summary_stats(session_id)
    body = _exit_summary_group(elapsed_s=elapsed_s, usage=usage, stats=stats)
    console.print()
    console.print(
        Panel.fit(
            body,
            title="[bold bright_cyan]KIP Agent · 下次再见[/]",
            border_style="bright_blue",
            padding=(0, 1),
        )
    )
