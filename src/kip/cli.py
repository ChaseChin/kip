"""REPL：prompt_toolkit + rich。"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.styles.defaults import default_ui_style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.keys import Keys
from rich.console import Console

from kip.agent import Agent, AgentContext
from kip.banner import print_welcome
from kip.config import AppConfig, load_config, save_config
from kip.first_run import default_config_missing, first_run_wizard
from kip.emitter import StepEmitter
from kip.exit_summary import print_exit_summary
from kip.llm_client import LLMClient
from kip.dev_md import resolve_dev_md_path
from kip.dev_md_ingest import ingest_dev_md_to_global_memory
from kip.emitter import THINKING_HINTS_DEV_MD
from kip.log_setup import reset_kip_logging_handlers, setup_logging
from kip.memory import MemoryStore
from kip.model_selector import interactive_setup, needs_setup, repl_llm_reconfigure
from kip.paths import resolve_config_relative
from kip.pixel_kip import kip_prompt_formatted_text
from kip.repl_completer import SlashCommandCompleter
from kip.repl_common import ReplBundle, UsageTracker, execute_repl_line
from kip.safety import SafetyGate
from kip.skills.loader import load_installed_skill_tools_report
from kip.soul import load_soul_markdown
from kip.tools import default_tools
from kip.tools.base import BaseTool
from kip.tools.skill_hub import InstallSkillTool, ListSkillsTool

try:
    from kip.mcp.client import discover_stdio_tools, merge_tools as merge_mcp_tools
except Exception:  # pragma: no cover
    discover_stdio_tools = None  # type: ignore[assignment]
    merge_tools = None  # type: ignore[assignment]

_log = logging.getLogger("kip.cli")

# 覆盖默认 bottom-toolbar「reverse」（易成近黑底 + 暗字）；用浅灰蓝底 + 亮字提升对比度
_REPL_PROMPT_STYLE = merge_styles(
    [
        default_ui_style(),
        Style.from_dict(
            {
                "bottom-toolbar": "bg:#6b7280 fg:#f9fafb",
                "bottom-toolbar.text": "fg:#f9fafb",
            }
        ),
    ]
)


async def _load_mcp_tools(cfg: AppConfig) -> list[BaseTool]:
    if not discover_stdio_tools or not cfg.mcp.servers:
        return []
    out: list[BaseTool] = []
    for spec in cfg.mcp.servers:
        label = str(spec.get("name", "srv"))
        cmd = str(spec.get("command", "python"))
        args = list(spec.get("args") or [])
        env = spec.get("env")
        env_s = {str(k): str(v) for k, v in (env or {}).items()} if env else None
        try:
            tools = await discover_stdio_tools(label, cmd, args, env_s)
            out.extend(tools)
        except Exception as e:
            _log.warning("mcp_load_failed label=%s err=%s", label, e)
            Console(stderr=True).print(f"[yellow]MCP {label} 加载失败: {e}[/yellow]")
    return out


def _resolve_skills_root(cfg: AppConfig) -> Path:
    return resolve_config_relative(cfg.paths.skills_dir)


def _short_display_path(p: Path, max_len: int = 48) -> str:
    s = str(p)
    if len(s) <= max_len:
        return s
    return "…" + s[-(max_len - 1) :]


def _print_input_border(console: Console) -> None:
    """输入区上下使用的浅色横线（宽度随终端略缩放）。"""
    try:
        cols = shutil.get_terminal_size().columns
    except OSError:
        cols = 80
    w = max(28, min(cols - 2, 96))
    console.print(f"[dim]{'─' * w}[/]")


async def _assemble_repl_bundle(
    cfg: AppConfig,
    *,
    startup_yolo: bool,
    fresh_session: bool,
    agent_holder: list[Agent | None],
    shared_console: Console | None = None,
    runtime_yolo: bool | None = None,
    trace_tools: bool = False,
) -> ReplBundle:
    """装配 REPL 依赖；`runtime_yolo` 非空时优先于 `startup_yolo`（用于 /setup all 后保留 YOLO 开关）。"""
    yolo_effective = runtime_yolo if runtime_yolo is not None else startup_yolo
    soul_text, _soul_path = load_soul_markdown(cfg)
    mem = MemoryStore(cfg.memory.db_path)
    await mem.connect()
    if fresh_session:
        session_id = await mem.create_session()
        history_msgs: list = []
    else:
        prev = await mem.get_latest_session_id()
        session_id = prev if prev else await mem.create_session()
        history_msgs = await mem.load_recent_messages(session_id, cfg.memory.max_history_messages)
    ctx = AgentContext(session_id=session_id, messages=history_msgs)
    emitter = (
        StepEmitter(console=shared_console, trace_tools=trace_tools)
        if shared_console is not None
        else StepEmitter(trace_tools=trace_tools)
    )
    console = emitter.console
    safety = SafetyGate(yolo=yolo_effective, enabled=cfg.safety.enabled)

    cwd = os.path.abspath(cfg.paths.cwd)
    base_tools = default_tools(cwd, cfg.safety.browser_allowed_hosts)
    mcp_extra = await _load_mcp_tools(cfg)

    skills_root = _resolve_skills_root(cfg)
    skills_root.mkdir(parents=True, exist_ok=True)
    loaded_skills, skill_load_errors = load_installed_skill_tools_report(skills_root, cwd)
    for err in skill_load_errors:
        Console(stderr=True).print(f"[yellow]Skill 加载跳过: {err}[/yellow]")

    def on_skill_installed(new_tools: list[BaseTool]) -> None:
        a = agent_holder[0]
        if a is not None:
            a.merge_tools(new_tools)

    install_skill_tool = InstallSkillTool(skills_root, cwd, on_skill_installed)
    list_skills_tool = ListSkillsTool(skills_root)

    core_tools: list[BaseTool] = [
        *base_tools,
        *loaded_skills,
        install_skill_tool,
        list_skills_tool,
    ]
    tools: list[BaseTool] = (
        merge_mcp_tools(core_tools, mcp_extra) if merge_mcp_tools else [*core_tools, *mcp_extra]
    )

    llm = LLMClient(cfg.llm)
    usage = UsageTracker()

    agent = Agent(
        cfg,
        llm,
        tools,
        mem,
        safety,
        emitter,
        on_token_usage=None,
        soul_markdown=soul_text,
    )
    agent_holder[0] = agent

    return ReplBundle(
        cfg=cfg,
        session_id=session_id,
        ctx=ctx,
        mem=mem,
        agent=agent,
        emitter=emitter,
        console=console,
        safety=safety,
        llm=llm,
        usage=usage,
        trace_tools=trace_tools,
    )


async def _rebundle_same_session(
    bundle: ReplBundle,
    agent_holder: list[Agent | None],
    *,
    cfg: AppConfig,
) -> None:
    """按新 cfg 重建 LLM / 工具 / Agent；保留当前会话、记忆库与 StepEmitter。"""
    soul_text, _ = load_soul_markdown(cfg)
    safety = SafetyGate(yolo=bundle.safety.yolo, enabled=cfg.safety.enabled)
    cwd = os.path.abspath(cfg.paths.cwd)
    base_tools = default_tools(cwd, cfg.safety.browser_allowed_hosts)
    mcp_extra = await _load_mcp_tools(cfg)
    skills_root = _resolve_skills_root(cfg)
    skills_root.mkdir(parents=True, exist_ok=True)
    loaded_skills, skill_load_errors = load_installed_skill_tools_report(skills_root, cwd)
    for err in skill_load_errors:
        Console(stderr=True).print(f"[yellow]Skill 加载跳过: {err}[/yellow]")

    def on_skill_installed(new_tools: list[BaseTool]) -> None:
        a = agent_holder[0]
        if a is not None:
            a.merge_tools(new_tools)

    install_skill_tool = InstallSkillTool(skills_root, cwd, on_skill_installed)
    list_skills_tool = ListSkillsTool(skills_root)
    core_tools: list[BaseTool] = [
        *base_tools,
        *loaded_skills,
        install_skill_tool,
        list_skills_tool,
    ]
    tools: list[BaseTool] = (
        merge_mcp_tools(core_tools, mcp_extra) if merge_mcp_tools else [*core_tools, *mcp_extra]
    )
    llm = LLMClient(cfg.llm)
    agent = Agent(
        cfg,
        llm,
        tools,
        bundle.mem,
        safety,
        bundle.emitter,
        on_token_usage=None,
        soul_markdown=soul_text,
    )
    agent_holder[0] = agent
    bundle.cfg = cfg
    bundle.llm = llm
    bundle.agent = agent
    bundle.safety = safety


async def _apply_setup_config_only(
    bundle: ReplBundle,
    agent_holder: list[Agent | None],
) -> None:
    """将 config 恢复默认后，始终进入与首次启动相同的 LLM 交互；不删数据库与日志。"""
    save_config(AppConfig())
    cfg = load_config()
    cfg = await asyncio.to_thread(repl_llm_reconfigure, cfg)
    await _rebundle_same_session(bundle, agent_holder, cfg=cfg)


async def _apply_setup_all(
    bundle: ReplBundle,
    agent_holder: list[Agent | None],
    *,
    startup_yolo: bool,
) -> None:
    """删除记忆库与日志，将 config 写回默认；不删除或重写 SOUL/DEV/skills 文件。"""
    cfg_old = bundle.cfg
    await bundle.mem.close()
    db_path = bundle.mem.path
    if db_path.is_file():
        try:
            db_path.unlink()
        except OSError as e:
            bundle.console.print(f"[yellow]无法删除记忆库文件: {e}[/yellow]")

    log_p = resolve_config_relative(cfg_old.paths.log_path)
    if log_p.is_file():
        try:
            log_p.unlink()
        except OSError:
            pass

    reset_kip_logging_handlers()
    save_config(AppConfig())
    cfg = load_config()
    setup_logging(cfg)
    cfg = await asyncio.to_thread(repl_llm_reconfigure, cfg)

    new_b = await _assemble_repl_bundle(
        cfg,
        startup_yolo=startup_yolo,
        fresh_session=True,
        agent_holder=agent_holder,
        shared_console=bundle.emitter.console,
        runtime_yolo=bundle.safety.yolo,
        trace_tools=bundle.trace_tools,
    )
    bundle.cfg = new_b.cfg
    bundle.session_id = new_b.session_id
    bundle.ctx = new_b.ctx
    bundle.mem = new_b.mem
    bundle.agent = new_b.agent
    bundle.emitter = new_b.emitter
    bundle.console = new_b.console
    bundle.safety = new_b.safety
    bundle.llm = new_b.llm
    bundle.usage = UsageTracker()
    bundle.trace_tools = new_b.trace_tools


async def run_repl(
    *, yolo: bool = False, load_dev_md: bool = False, trace_tools: bool = False
) -> None:
    asyncio.get_running_loop().set_debug(False)

    cfg = load_config()
    setup_logging(cfg)
    if default_config_missing():
        cfg = first_run_wizard(cfg)
    elif needs_setup(cfg):
        cfg = interactive_setup(cfg)

    agent_holder: list[Agent | None] = [None]
    bundle = await _assemble_repl_bundle(
        cfg,
        startup_yolo=yolo,
        fresh_session=False,
        agent_holder=agent_holder,
        trace_tools=trace_tools,
    )
    soul_text, soul_path = load_soul_markdown(bundle.cfg)
    soul_show = _short_display_path(soul_path)

    started = time.monotonic()

    kb = KeyBindings()

    @kb.add(Keys.BackTab, eager=True)
    def _toggle_yolo(event: KeyPressEvent) -> None:
        """Shift+Tab：切换 YOLO（跳过大部分安全确认）。"""
        bundle.safety.set_yolo(not bundle.safety.yolo)
        event.app.invalidate()

    def bottom_toolbar() -> HTML:
        yolo_tag = (
            "<style fg='#facc15'><b>YOLO·开</b></style>"
            if bundle.safety.yolo
            else "<style fg='#d1d5db'>YOLO·关</style>"
        )
        cw = bundle.cfg.llm.context_window
        cw_show = "默认" if cw is None else str(cw)
        return HTML(
            f"<style fg='#f9fafb'>模型 {bundle.cfg.llm.model} | "
            f"max_output={bundle.cfg.llm.max_output_tokens} | "
            f"context window={cw_show} | </style>"
            f"{yolo_tag}"
            f"<style fg='#f9fafb'> | Shift+Tab YOLO | /help</style>"
        )

    session = PromptSession(
        style=_REPL_PROMPT_STYLE,
        message=kip_prompt_formatted_text(),
        bottom_toolbar=bottom_toolbar,
        key_bindings=kb,
        multiline=False,
        completer=SlashCommandCompleter(),
        complete_while_typing=True,
        complete_style=CompleteStyle.COLUMN,
        reserve_space_for_menu=10,
        placeholder=HTML(
            '<style fg="ansibrightblack">输入问题或指令，例如 /help、/setup、/model、/clear…（输入 / 可调命令补全）</style>'
        ),
    )

    console = bundle.console
    print_welcome(
        console,
        bundle.cfg,
        yolo=bundle.safety.yolo,
        soul_loaded=bool(soul_text),
        soul_path_show=soul_show,
    )

    dev_path = resolve_dev_md_path(bundle.cfg)
    if load_dev_md and dev_path.is_file():
        try:
            async with bundle.emitter.thinking(hints=THINKING_HINTS_DEV_MD):
                n, msg = await ingest_dev_md_to_global_memory(
                    bundle.llm, bundle.mem, bundle.cfg, dev_path
                )
            console.print(f"[dim]{msg}[/dim]")
            _log.info("dev_md_startup_ingest count=%s path=%s", n, dev_path)
        except Exception as e:
            _log.exception("dev_md_startup_ingest_failed")
            console.print(f"[yellow]DEV.MD 启动加载失败: {e}[/yellow]")

    _log.info(
        "repl_ready model=%s yolo=%s session_id=%s db=%s",
        bundle.cfg.llm.model,
        bundle.safety.yolo,
        bundle.session_id,
        bundle.mem.path,
    )

    eof_streak = 0
    while True:
        _print_input_border(console)
        line: str | None = None
        while True:
            try:
                # 须用 prompt_async 与 asyncio.run(main) 同一事件循环；勿 run_in_executor(session.prompt)，
                # 否则 prompt_toolkit 在子线程里 create_task 会触发「Non-thread-safe operation…」。
                line = await session.prompt_async()
            except EOFError:
                eof_streak += 1
                if eof_streak >= 2:
                    _log.info("repl_input_eof_double_quit")
                    line = None
                    break
                _log.info("repl_input_eof_once_need_second")
                console.print("[dim]再按一次 Ctrl+D 退出[/dim]")
                continue
            except KeyboardInterrupt:
                eof_streak = 0
                _log.info("repl_input_keyboard_interrupt")
                console.print("^C")
                continue
            if (line or "").strip():
                eof_streak = 0
                break
            # 空行回车：不画下边框、不执行，仅再次 prompt（避免多打换行与重复横线）
        if line is None:
            break

        _print_input_border(console)
        result = await execute_repl_line(bundle, line)
        if result == "setup_config":
            await _apply_setup_config_only(bundle, agent_holder)
            bundle.console.print("[green]LLM 已重新配置（记忆库与日志未删除），可继续对话。[/green]")
            continue
        if result == "setup_all":
            await _apply_setup_all(bundle, agent_holder, startup_yolo=yolo)
            bundle.console.print("[green]LLM 已重新配置，记忆库与日志已清空，已使用新会话。[/green]")
            continue
        if result == "quit":
            break

    elapsed = time.monotonic() - started
    _log.info(
        "repl_exit_loop session_id=%s elapsed_s=%.2f tokens_prompt=%s tokens_completion=%s",
        bundle.session_id,
        elapsed,
        bundle.usage.prompt,
        bundle.usage.completion,
    )
    await print_exit_summary(
        console,
        elapsed_s=elapsed,
        usage=bundle.usage,
        mem=bundle.mem,
        session_id=bundle.session_id,
    )
    _log.info("repl_memory_close session_id=%s", bundle.session_id)
    await bundle.mem.close()
