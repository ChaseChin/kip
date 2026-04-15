"""回复区品牌样式：KIP Agent Logo 与面板装饰。"""

from __future__ import annotations

from rich.markdown import Markdown
from rich.panel import Panel

# 欢迎横幅等：机器人图标（与「思考中」一致）
AGENT_ICON_MARKUP = "[bold bright_magenta]🤖[/]"
# 助手回复面板顶栏：报告/汇报态图标（最终结果呈现）
REPLY_PANEL_ICON_MARKUP = "[bold cyan]📋[/]"


def agent_reply_title() -> str:
    """回复面板顶栏（📋 报告图标 + KIP Agent · 成功执行）。"""
    return (
        f"{REPLY_PANEL_ICON_MARKUP} "
        "[bold bright_cyan]K[/][bold cyan]I[/][bold blue]P[/] [white bold]Agent[/]"
        " [dim]· 成功执行[/]"
    )


def assistant_reply_panel(markdown_text: str) -> Panel:
    """生成助手回复面板：标题栏含图标与品牌文案，正文为 Markdown。"""
    return Panel(
        Markdown(markdown_text),
        border_style="bright_blue",
        padding=(1, 2),
        title=agent_reply_title(),
        title_align="left",
    )
