"""启动欢迎界面：Logo 与运行信息。"""

from __future__ import annotations

import platform

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from kip.branding import AGENT_ICON_MARKUP
from kip.config import AppConfig
from kip.pixel_kip import build_kip_pixel_text


def print_welcome(
    console: Console,
    cfg: AppConfig,
    *,
    yolo: bool,
    soul_loaded: bool = False,
    soul_path_show: str = "",
) -> None:
    """在 REPL 进入主循环前打印 Logo 与配置摘要。"""
    from kip import __version__

    kip_art = build_kip_pixel_text()

    base = (cfg.llm.base_url or "").strip()
    base_show = base if len(base) <= 46 else base[:43] + "…"
    ctx = cfg.llm.context_window

    subtitle = Text.from_markup(
        "[dim]对话式命令行 AI · 输入即对话，[/][bold white]/help[/][dim] 查看命令[/]"
    )

    rows: list[Text | str] = [
        kip_art,
        Text(""),
        subtitle,
        Text(""),
        Text.from_markup(f"[dim]版本[/]        [cyan]{__version__}[/]"),
        Text.from_markup(f"[dim]模型[/]        [green]{cfg.llm.model}[/]"),
        Text.from_markup(
            f"[dim]接口[/]        [white]{base_show or '(默认 endpoint)'}[/]"
        ),
        Text.from_markup(f"[dim]API Key[/]     [dim]{cfg.llm.api_key_env}[/]"),
        Text.from_markup(f"[dim]max_output[/]  {cfg.llm.max_output_tokens}"),
        (
            Text.from_markup(f"[dim]context[/]     [cyan]{ctx}[/]")
            if ctx
            else Text.from_markup("[dim]context[/]     [dim]模型默认[/]")
        ),
        Text.from_markup(
            f"[dim]YOLO[/]        {'[yellow]开[/]' if yolo else '[dim]关[/]'}"
        ),
        Text.from_markup(f"[dim]记忆库[/]      [dim]{cfg.memory.db_path}[/]"),
    ]
    if soul_path_show:
        if soul_loaded:
            rows.append(
                Text.from_markup(
                    f"[dim]SOUL[/]         [green]已加载[/] [dim]{soul_path_show}[/]"
                )
            )
        else:
            rows.append(
                Text.from_markup(
                    f"[dim]SOUL[/]         [yellow]未找到[/] [dim]{soul_path_show}[/] "
                    f"[dim]（使用内置默认人设）[/]"
                )
            )
    if platform.system() == "Darwin":
        rows.append(
            Text.from_markup(
                "[dim]AppleScript[/] [green]run_applescript[/] [dim]已加载（内置工具）[/]"
            )
        )

    # 标题栏 KIP 三色与像素字 rgb 一致
    panel_title = (
        f"{AGENT_ICON_MARKUP} [bold rgb(56,189,248)]K[/][bold rgb(232,121,250)]I[/]"
        f"[bold rgb(250,204,21)]P[/] [bold white]Agent[/]"
    )

    console.print()
    console.print(
        Panel.fit(
            Group(*rows),
            title=panel_title,
            title_align="left",
            border_style="bright_blue",
            padding=(1, 2),
            style="on #1a2332",
        )
    )
    console.print(
        "[dim]输入 /help 查看命令 · Ctrl+D 退出 · 直接输入问题与 Agent 对话[/]\n"
    )
