"""SOUL.MD 加载与路径解析。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from kip.config import AppConfig, PathsConfig
from kip.soul import load_soul_markdown, resolve_soul_path


def test_resolve_soul_path_relative_to_repo() -> None:
    cfg = AppConfig(paths=PathsConfig(soul_path="SOUL.MD"))
    p = resolve_soul_path(cfg)
    assert p.name == "SOUL.MD"
    assert p.is_absolute()


def test_load_soul_from_temp_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "my.md"
        f.write_text("# 人设\n\n你好。", encoding="utf-8")
        cfg = AppConfig(paths=PathsConfig(soul_path=str(f)))
        text, path = load_soul_markdown(cfg)
        assert path == f.resolve()
        assert "人设" in text
        assert "你好" in text


def test_load_soul_missing_returns_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg = AppConfig(paths=PathsConfig(soul_path=str(Path(td) / "nope.md")))
        text, path = load_soul_markdown(cfg)
        assert text == ""
        assert path.name == "nope.md"


@pytest.mark.asyncio
async def test_agent_system_prompt_includes_soul() -> None:
    from kip.agent import Agent
    from kip.emitter import StepEmitter
    from kip.llm_client import LLMClient
    from kip.memory import MemoryStore
    from kip.safety import SafetyGate

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "d.db"
        cfg = AppConfig()
        cfg.memory.long_term_inject_max = 0
        mem = MemoryStore(str(db))
        await mem.connect()
        agent = Agent(
            cfg,
            LLMClient(cfg.llm),
            [],
            mem,
            SafetyGate(yolo=True),
            StepEmitter(),
            soul_markdown="**人设**：测试机器人。",
        )
        sp = await agent._build_system_prompt()
        assert "人设与规则（SOUL）" in sp
        assert "测试机器人" in sp
        await mem.close()


def test_kip_soul_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("env soul", encoding="utf-8")
    monkeypatch.setenv("KIP_SOUL", str(p))
    cfg = AppConfig(paths=PathsConfig(soul_path="SOUL.MD"))
    text, resolved = load_soul_markdown(cfg)
    assert resolved == p.resolve()
    assert text == "env soul"
    monkeypatch.delenv("KIP_SOUL", raising=False)
