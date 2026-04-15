"""内置工具（无 LLM、尽量无网络）。"""

from __future__ import annotations

import platform
import tempfile
from pathlib import Path

import pytest

from kip.tools import default_tools
from kip.tools.file_io import ReadFileTool, WriteFileTool
from kip.tools.shell_exec import ShellExecTool


def test_default_tools_includes_run_applescript() -> None:
    names = [t.name for t in default_tools(".", [])]
    assert "run_applescript" in names
    assert "read_file" in names
    # install_skill / list_skills 由 cli 组装，不在 default_tools 内
    assert "install_skill" not in names


def test_skill_hub_tool_classes() -> None:
    from kip.tools.skill_hub import InstallSkillTool, ListSkillsTool

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "s"
        root.mkdir()
        a = InstallSkillTool(root, ".", lambda _: None)
        b = ListSkillsTool(root)
        assert a.name == "install_skill"
        assert b.name == "list_skills"


@pytest.mark.asyncio
async def test_read_write_file_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.txt"
        w = WriteFileTool()
        r = ReadFileTool()
        out = await w.execute({"path": str(p), "content": "kip-test"})
        assert "已写入" in out
        text = await r.execute({"path": str(p)})
        assert "kip-test" in text


@pytest.mark.asyncio
async def test_shell_exec_echo() -> None:
    with tempfile.TemporaryDirectory() as td:
        sh = ShellExecTool(cwd=td)
        out = await sh.execute({"command": "echo shell_ok"})
        assert "shell_ok" in out


@pytest.mark.asyncio
async def test_run_applescript_macos_only() -> None:
    from kip.tools.applescript import AppleScriptTool

    t = AppleScriptTool()
    out = await t.execute({"script": 'return "as-ok"'})
    if platform.system() == "Darwin":
        assert "as-ok" in out
    else:
        assert "macOS" in out or "Darwin" in out or "仅" in out
