"""REPL 斜杠命令补全：在输入 `/…` 时提供类似 Claude Code 的候选列表（prompt_toolkit）。"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING

from prompt_toolkit.completion import Completer, Completion

if TYPE_CHECKING:
    from prompt_toolkit.document import Document

# (命令名不含 /, 简短说明)
SLASH_COMMAND_ITEMS: list[tuple[str, str]] = [
    ("help", "完整帮助（含 config）"),
    ("h", "速览帮助"),
    ("?", "同速览"),
    ("clear", "清空本会话消息"),
    ("memory", "搜索长期记忆"),
    ("model", "查看或切换模型"),
    ("stats", "本会话 Token"),
    ("tools", "列出已加载工具"),
    ("skills", "列出已安装 skill"),
    ("loaddev", "DEV.MD → 长期记忆"),
    ("safety", "on / off"),
    ("yolo", "切换 YOLO"),
    ("setup", "重配 LLM；可接 all、force"),
    ("exit", "退出"),
    ("quit", "退出"),
    ("q", "退出"),
]


class SlashCommandCompleter(Completer):
    """仅在当前行输入 `/命令名`（第一个 token）或部分子命令时给出补全。"""

    def get_completions(
        self,
        document: Document,
        complete_event: object,
    ) -> Iterable[Completion]:
        del complete_event  # 协议要求，未使用
        text = document.text_before_cursor
        if "\n" in text:
            return

        # 子命令：/setup …、/loaddev …、/safety …
        yield from _complete_setup_sub(text)
        yield from _complete_loaddev_sub(text)
        yield from _complete_safety_sub(text)

        # 主命令：整行仅为「空白 + /xxx」且尚未出现第二个 token
        m = re.match(r"^(\s*)(/[^\s]*)$", text)
        if not m:
            return
        ws, slash_part = m.group(1), m.group(2)
        if slash_part == "/":
            prefix = ""
        else:
            prefix = slash_part[1:].lower()

        replace_len = len(text)
        for name, meta in SLASH_COMMAND_ITEMS:
            if prefix and not name.startswith(prefix):
                continue
            inserted = f"{ws}/{name}"
            yield Completion(
                inserted,
                start_position=-replace_len,
                display=f"/{name}",
                display_meta=meta,
            )


def _complete_setup_sub(text: str) -> Iterable[Completion]:
    """`/setup ` 后接 all / force（部分输入也可过滤）。"""
    m = re.match(r"^(\s*/setup\s+)(\S*)$", text, flags=re.IGNORECASE)
    if not m:
        return
    base, partial = m.group(1), m.group(2).lower()
    opts = [
        ("all", "同时清空记忆库与日志"),
        ("force", "跳过确认"),
    ]
    for word, meta in opts:
        if partial and not word.startswith(partial):
            continue
        full = f"{base}{word}"
        yield Completion(
            full,
            start_position=-len(text),
            display=word,
            display_meta=meta,
        )


def _complete_loaddev_sub(text: str) -> Iterable[Completion]:
    m = re.match(r"^(\s*/loaddev\s+)(\S*)$", text, flags=re.IGNORECASE)
    if not m:
        return
    base, partial = m.group(1), m.group(2).lower()
    word, meta = "force", "忽略内容未变，强制提炼"
    if partial and not word.startswith(partial):
        return
    yield Completion(
        f"{base}{word}",
        start_position=-len(text),
        display=word,
        display_meta=meta,
    )


def _complete_safety_sub(text: str) -> Iterable[Completion]:
    m = re.match(r"^(\s*/safety\s+)(\S*)$", text, flags=re.IGNORECASE)
    if not m:
        return
    base, partial = m.group(1), m.group(2).lower()
    for word, meta in (("on", "开启安全确认"), ("off", "关闭安全确认")):
        if partial and not word.startswith(partial):
            continue
        yield Completion(
            f"{base}{word}",
            start_position=-len(text),
            display=word,
            display_meta=meta,
        )
