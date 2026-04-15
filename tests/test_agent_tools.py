"""Agent 工具合并。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from kip.agent import Agent
from kip.config import AppConfig
from kip.emitter import StepEmitter
from kip.llm_client import LLMClient
from kip.memory import MemoryStore
from kip.safety import SafetyGate
from kip.tools.base import BaseTool


class _DummyTool(BaseTool):
    name = "dummy_x"
    description = "test"
    is_safe = True

    @property
    def schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, args):
        return "ok"


def test_agent_merge_and_list_tools() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "t.db"
        cfg = AppConfig()
        llm = LLMClient(cfg.llm)
        mem = MemoryStore(str(db))
        agent = Agent(
            cfg,
            llm,
            [],
            mem,
            SafetyGate(yolo=True),
            StepEmitter(),
        )
        assert agent.list_tools() == []
        agent.merge_tools([_DummyTool()])
        names = [t.name for t in agent.list_tools()]
        assert "dummy_x" in names
