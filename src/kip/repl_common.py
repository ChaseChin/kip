"""REPL 共享：解析命令与执行一轮对话。"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from rich.console import Console

from kip.dev_md import append_turn as append_dev_md_turn, resolve_dev_md_path
from kip.log_setup import preview_text
from kip.paths import resolve_config_relative
from kip.repl_help import print_repl_help, print_repl_help_short
from kip.repl_cancel import await_with_esc_cancel
from kip.safety import prompt_one_line

if TYPE_CHECKING:
    from kip.agent import Agent, AgentContext
    from kip.config import AppConfig
    from kip.emitter import StepEmitter
    from kip.llm_client import LLMClient
    from kip.memory import MemoryStore
    from kip.safety import SafetyGate
    from kip.tools.base import BaseTool


def parse_slash(line: str) -> tuple[str, str]:
    line = line.strip()
    if not line.startswith("/"):
        return "", line
    parts = line.split(maxsplit=1)
    cmd = parts[0].lower().lstrip("/")
    rest = parts[1] if len(parts) > 1 else ""
    return cmd, rest


_log = logging.getLogger("kip.repl")


@dataclass
class UsageTracker:
    prompt: int = 0
    completion: int = 0
    session_total: int = 0


@dataclass
class ReplBundle:
    cfg: Any  # AppConfig
    session_id: str
    ctx: Any  # AgentContext
    mem: Any  # MemoryStore
    agent: Any  # Agent
    emitter: Any  # StepEmitter
    console: Console
    safety: Any  # SafetyGate
    llm: Any  # LLMClient
    usage: UsageTracker = field(default_factory=UsageTracker)
    trace_tools: bool = False


async def execute_repl_line(
    bundle: ReplBundle,
    line: str,
) -> Literal["continue", "quit", "setup_config", "setup_all"]:
    """处理一行输入：返回 continue、quit，或 /setup 触发的重置标记。"""
    if not (line or "").strip():
        return "continue"

    cmd, text = parse_slash(line)
    console = bundle.console
    cfg = bundle.cfg
    mem = bundle.mem
    ctx = bundle.ctx
    emitter = bundle.emitter
    safety = bundle.safety
    session_id = bundle.session_id
    ut = bundle.usage

    if cmd:
        if cmd in ("quit", "exit", "q"):
            return "quit"
        if cmd == "help" or line.strip() == "?":
            print_repl_help(console)
            return "continue"
        if cmd in ("h", "?"):
            print_repl_help_short(console)
            return "continue"
        if cmd == "clear":
            _log.info("slash_command cmd=/clear session_id=%s", session_id)
            ctx.messages.clear()
            await mem.clear_session_messages(session_id)
            console.print("已清空会话消息。")
            return "continue"
        if cmd == "memory":
            rows = await mem.search_memories(text.strip() or "%", limit=30)
            if not rows:
                console.print("无匹配记忆。")
            else:
                for r in rows:
                    console.print(f"  [cyan]{r['key']}[/cyan]: {r['value'][:200]}")
            return "continue"
        if cmd == "loaddev":
            from kip.dev_md_ingest import ingest_dev_md_to_global_memory
            from kip.emitter import THINKING_HINTS_DEV_MD

            parts = text.strip().split()
            force = bool(parts) and parts[0].lower() == "force"
            path = resolve_dev_md_path(cfg)
            try:
                async with emitter.thinking(hints=THINKING_HINTS_DEV_MD):
                    n, msg = await ingest_dev_md_to_global_memory(
                        bundle.llm, mem, cfg, path, force=force
                    )
                if n:
                    console.print(f"[green]{msg}[/green]")
                else:
                    console.print(f"[dim]{msg}[/dim]")
            except Exception as e:
                _log.exception("loaddev_failed")
                console.print(f"[red]加载失败:[/red] {e}")
            return "continue"
        if cmd == "model":
            if text.strip():
                cfg.llm.model = text.strip()
                from kip.config import save_config

                save_config(cfg)
                console.print(f"已切换模型: {cfg.llm.model}")
            else:
                console.print(f"当前模型: {cfg.llm.model}")
            return "continue"
        if cmd == "stats":
            console.print(
                f"Token: prompt={ut.prompt} completion={ut.completion} "
                f"total={ut.prompt + ut.completion}"
            )
            return "continue"
        if cmd == "tools":
            for t in bundle.agent.list_tools():
                s = "安全" if t.is_safe else "需确认"
                console.print(f"  • [green]{t.name}[/green] ({s}) — {t.description[:80]}")
            return "continue"
        if cmd == "skills":
            from kip.skills.manifest import read_manifest

            root = resolve_config_relative(bundle.cfg.paths.skills_dir)
            if not root.is_dir():
                console.print("暂无 skills 目录。")
                return "continue"
            any_ok = False
            for p in sorted(root.iterdir()):
                if not p.is_dir() or not (p / "skill.json").is_file():
                    continue
                any_ok = True
                try:
                    m = read_manifest(p / "skill.json")
                    console.print(f"  • [cyan]{m.id}[/cyan] {m.name} v{m.version}")
                except Exception as e:
                    console.print(f"  • [yellow]{p.name}[/yellow] 读取失败: {e}")
            if not any_ok:
                console.print("未安装任何 skill（目录需含 skill.json）。")
            return "continue"
        if cmd == "safety":
            low = text.strip().lower()
            if low in ("off", "false", "0"):
                safety.set_enabled(False)
                console.print("安全确认已关闭（仍受 YOLO/删除规则约束）。")
            elif low in ("on", "true", "1", ""):
                safety.set_enabled(True)
                console.print("安全确认已开启。")
            return "continue"
        if cmd == "yolo":
            safety.set_yolo(not safety.yolo)
            console.print(f"YOLO = {safety.yolo}")
            return "continue"
        if cmd == "setup":
            parts = text.strip().lower().split()
            all_mode = "all" in parts
            force = "force" in parts
            if not force:
                if all_mode:
                    console.print(
                        "[yellow]/setup all[/yellow]：将 [bold]config.yaml[/bold] 恢复为默认并"
                        "删除记忆库（SQLite）与当前日志文件，随后进入与 [bold]首次启动相同[/bold] 的 LLM 引导；"
                        "[bold]不会[/bold]删除、覆盖或按首次向导重建 [bold]SOUL.MD、DEV.MD[/bold] 与 [bold]skills[/bold] 目录中的内容。"
                    )
                else:
                    console.print(
                        "[yellow]/setup[/yellow]：将 [bold]config.yaml[/bold] 恢复为默认，然后进入与 [bold]首次启动相同[/bold] 的"
                        "模型与 API Key 交互；不删除记忆库与日志；"
                        "[bold]不会[/bold]删除、覆盖或按首次向导重建 [bold]SOUL、DEV、skills[/bold]。"
                    )
                ans = await prompt_one_line("确认请输入 yes，其它键取消: ")
                if (ans or "").strip().lower() != "yes":
                    console.print("[dim]已取消。[/dim]")
                    return "continue"
            return "setup_all" if all_mode else "setup_config"
        console.print(f"[yellow]未知命令 /{cmd}，输入 /help[/yellow]")
        return "continue"

    user_line = line.strip()
    if not user_line:
        return "continue"

    await mem.touch_session(session_id)
    try:
        emitter.reset_step()
        _log.info(
            "user_turn session_id=%s len=%d preview=%r",
            session_id,
            len(user_line),
            preview_text(user_line),
        )
        console.print("[cyan]🤖 KIP Agent 思考中... (esc 取消)[/cyan]")
        t_turn0 = time.monotonic()
        result = await await_with_esc_cancel(
            bundle.agent.run_turn(ctx, user_line),
            console=console,
        )
        elapsed_turn_s = time.monotonic() - t_turn0
        ut.prompt += result.usage_prompt
        ut.completion += result.usage_completion
        ut.session_total += result.usage_prompt + result.usage_completion
        turn_tokens = result.usage_prompt + result.usage_completion
        console.print()
        emitter.markdown_reply(
            result.text,
            elapsed_s=elapsed_turn_s,
            turn_tokens=turn_tokens,
            session_tokens=ut.session_total,
        )
        append_dev_md_turn(
            user_line,
            result.text,
            dev_md=resolve_dev_md_path(cfg),
        )
    except asyncio.CancelledError:
        _log.info("user_turn_cancelled session_id=%s", session_id)
        return "continue"
    except Exception as e:
        _log.exception("user_turn_failed session_id=%s", session_id)
        console.print(f"[red]错误:[/red] {e}")

    return "continue"
