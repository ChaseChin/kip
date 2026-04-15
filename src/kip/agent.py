"""Agent：多轮工具链与上下文构建。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from kip.config import AppConfig
from kip.log_setup import preview_text
from kip.emitter import (
    THINKING_HINTS_FIRST,
    THINKING_HINTS_FOLLOWUP,
    StepEmitter,
    format_tool_args_preview,
)
from kip.llm_client import LLMClient, parse_assistant_message, repair_json_args
from kip.memory import MemoryStore
from kip.memory_extract import maybe_extract_long_term_memories
from kip.safety import SafetyGate
from kip.tools.base import BaseTool

_log = logging.getLogger("kip.agent")


def _timing_enabled() -> bool:
    return os.environ.get("KIP_TIMING", "").strip().lower() in ("1", "true", "yes")


@dataclass
class AgentResult:
    text: str
    usage_prompt: int = 0
    usage_completion: int = 0


@dataclass
class AgentContext:
    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        cfg: AppConfig,
        llm: LLMClient,
        tools: Sequence[BaseTool],
        memory: MemoryStore,
        safety: SafetyGate,
        emitter: StepEmitter,
        on_token_usage: Callable[[int, int], Any] | None = None,
        soul_markdown: str = "",
    ) -> None:
        self._cfg = cfg
        self._llm = llm
        self._tools = {t.name: t for t in tools}
        self._memory = memory
        self._safety = safety
        self._emitter = emitter
        self._on_usage = on_token_usage
        self._soul_markdown = soul_markdown.strip()
        self._system_prompt_base = (
            "你是 KIP CLI，帮助用户完成任务。优先使用工具获取真实信息。"
            "回答简洁，必要时使用 Markdown。"
            "当前会话已加载 KIP 内置工具列表（见 tools）；其中 run_applescript 为 macOS 内置，"
            "无需用户执行 install_skill。"
            "install_skill 仅用于安装扩展 skill 目录，不要声称内置工具「未安装」。"
        )

    async def _build_system_prompt(self) -> str:
        parts: list[str] = [self._system_prompt_base]
        if self._soul_markdown:
            parts.append("## 人设与规则（SOUL）\n" + self._soul_markdown)
        base = "\n\n".join(parts)
        n = self._cfg.memory.long_term_inject_max
        if n <= 0:
            return base
        rows = await self._memory.list_global_memories_latest(limit=n)
        if not rows:
            return base
        block = "\n".join(f"- {k}: {v}" for k, v in rows)
        return f"{base}\n\n## 长期记忆（跨会话）\n{block}\n"

    def merge_tools(self, extra: Sequence[BaseTool]) -> None:
        """运行时注册新工具（例如安装 skill 之后）。"""
        for t in extra:
            self._tools[t.name] = t

    def list_tools(self) -> list[BaseTool]:
        """当前已注册工具（含运行时安装的 skill）。"""
        return list(self._tools.values())

    def _openai_tools(self) -> list[dict[str, Any]]:
        return [t.to_openai_tool() for t in self._tools.values()]

    def _trim_messages(self, msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        max_m = self._cfg.memory.max_history_messages
        if len(msgs) <= max_m:
            return msgs
        return msgs[-max_m:]

    async def _run_tool(
        self,
        name: str,
        arguments: str,
        tool_call_id: str,
        session_id: str,
    ) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"未知工具: {name}"
        args = repair_json_args(arguments)
        preview = format_tool_args_preview(args)
        _log.info("tool_execute name=%s safe=%s args_preview=%s", name, tool.is_safe, preview[:300])
        self._emitter.tool_line(name, preview)
        self._emitter.step_start(f"执行工具 {name}")
        try:
            if not tool.is_safe:
                ok = await self._safety.confirm(f"{name}({preview})")
                if not ok:
                    msg = "用户取消了该操作"
                    self._emitter.step_fail(msg)
                    await self._memory.log_tool(
                        session_id, name, {"args": args}, "cancelled"
                    )
                    return msg
            out = await tool.execute(args)
            self._emitter.step_ok(out[:500] + ("..." if len(out) > 500 else ""))
            await self._memory.log_tool(session_id, name, {"args": args}, "ok")
            return out
        except Exception as e:
            self._emitter.step_fail(str(e))
            await self._memory.log_tool(
                session_id, name, {"args": args, "error": str(e)}, "error"
            )
            return f"工具错误: {e}"

    def _accumulate_usage(self, resp: dict[str, Any]) -> None:
        u = resp.get("usage") or {}
        pt = int(u.get("prompt_tokens") or 0)
        ct = int(u.get("completion_tokens") or 0)
        if self._on_usage and (pt or ct):
            self._on_usage(pt, ct)

    async def _extract_long_term_background(
        self, user_text: str, assistant_text: str
    ) -> None:
        """不阻塞主回复；失败静默（与原先 try/except pass 一致）。"""
        try:
            await maybe_extract_long_term_memories(
                self._llm,
                self._memory,
                self._cfg.memory,
                user_text,
                assistant_text,
            )
        except Exception as e:
            _log.warning("long_term_extract_failed: %s", e)

    async def run_turn(self, ctx: AgentContext, user_text: str) -> AgentResult:
        """处理单轮用户输入（可多步工具）。"""
        t_wall0 = time.monotonic()
        timing = _timing_enabled()
        prep_ms = 0.0
        llm_ms = 0.0
        tools_ms = 0.0

        sid = ctx.session_id
        user_msg: dict[str, Any] = {"role": "user", "content": user_text}
        ctx.messages.append(user_msg)
        await self._memory.append_message(sid, user_msg)

        _log.info(
            "turn_start session_id=%s user_len=%d preview=%r",
            sid,
            len(user_text),
            preview_text(user_text),
        )

        system_content = await self._build_system_prompt()
        if timing:
            prep_ms = (time.monotonic() - t_wall0) * 1000
        msgs: list[dict[str, Any]] = (
            [{"role": "system", "content": system_content}]
            + self._trim_messages(ctx.messages)
        )
        tools = self._openai_tools()
        total_prompt = 0
        total_completion = 0
        first_llm_round = True
        # 上一轮若执行了工具，本轮在 spinner 前先打一行，避免「工具跑完到下次 LLM」之间像卡死
        pending_integrate_hint = False

        while True:
            hints = THINKING_HINTS_FIRST if first_llm_round else THINKING_HINTS_FOLLOWUP
            if pending_integrate_hint:
                self._emitter.info(
                    "[cyan]⏳[/] [dim]工具结果已就绪，正在调用模型整合回复…[/]"
                )
                pending_integrate_hint = False
            t_llm0 = time.monotonic()
            async with self._emitter.thinking(hints=hints):
                resp = await self._llm.chat(msgs, tools=tools)
            if timing:
                llm_ms += (time.monotonic() - t_llm0) * 1000
            first_llm_round = False
            self._accumulate_usage(resp)
            u = resp.get("usage") or {}
            total_prompt += int(u.get("prompt_tokens") or 0)
            total_completion += int(u.get("completion_tokens") or 0)

            asst = parse_assistant_message(resp)
            tool_calls = asst.get("tool_calls")

            if not tool_calls:
                text = asst.get("content") or ""
                ctx.messages.append(
                    {"role": "assistant", "content": text, "tool_calls": None}
                )
                await self._memory.append_message(
                    sid, {"role": "assistant", "content": text}
                )
                if self._cfg.memory.auto_extract_long_term:
                    asyncio.create_task(
                        self._extract_long_term_background(user_text, text)
                    )
                if timing:
                    wall_ms = (time.monotonic() - t_wall0) * 1000
                    extra = f" | 工具 {tools_ms:.0f}ms" if tools_ms > 0 else ""
                    self._emitter.info(
                        f"[dim]⏱ {wall_ms:.0f}ms 总耗时 | 准备/DB {prep_ms:.0f}ms | "
                        f"LLM {llm_ms:.0f}ms{extra} | 长期记忆提取已后台执行[/dim]"
                    )
                wall_s = time.monotonic() - t_wall0
                _log.info(
                    "turn_done session_id=%s prompt_tokens=%s completion_tokens=%s wall_s=%.2f",
                    sid,
                    total_prompt,
                    total_completion,
                    wall_s,
                )
                return AgentResult(
                    text=text,
                    usage_prompt=total_prompt,
                    usage_completion=total_completion,
                )

            ctx.messages.append(asst)
            await self._memory.append_message(sid, asst)

            for tc in tool_calls:
                tid = tc.get("id", "")
                fn = (tc.get("function") or {})
                name = fn.get("name", "")
                arguments = fn.get("arguments") or "{}"
                t_tool0 = time.monotonic()
                out = await self._run_tool(name, arguments, tid, sid)
                if timing:
                    tools_ms += (time.monotonic() - t_tool0) * 1000
                tool_msg: dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tid,
                    "name": name,
                    "content": out,
                }
                ctx.messages.append(tool_msg)
                await self._memory.append_message(sid, tool_msg)

            pending_integrate_hint = True

            msgs = (
                [{"role": "system", "content": system_content}]
                + self._trim_messages(ctx.messages)
            )
