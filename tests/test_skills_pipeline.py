"""Skill 安装与加载（使用 examples/skill_echo）。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kip.skills.install import install_skill_source
from kip.skills.loader import load_tools_from_skill_dir
from kip.skills.manifest import SkillManifest, read_manifest


def _example_skill_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "skill_echo"


@pytest.mark.skipif(
    not (_example_skill_dir() / "skill.json").is_file(),
    reason="examples/skill_echo 不存在",
)
def test_read_example_manifest() -> None:
    m = read_manifest(_example_skill_dir() / "skill.json")
    assert isinstance(m, SkillManifest)
    assert m.id == "skill_echo"
    assert m.module == "echo_tools"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (_example_skill_dir() / "skill.json").is_file(),
    reason="examples/skill_echo 不存在",
)
async def test_install_and_load_echo_skill() -> None:
    src = str(_example_skill_dir().resolve())
    with tempfile.TemporaryDirectory() as td:
        skills_root = Path(td) / "skills"
        dest = await install_skill_source(skills_root, src)
        assert dest.name == "skill_echo"
        tools = load_tools_from_skill_dir(dest, ".")
        names = [t.name for t in tools]
        assert "skill_echo__echo_text" in names
        echo = next(t for t in tools if t.name == "skill_echo__echo_text")
        out = await echo.execute({"text": "ping"})
        assert out == "ping"


@pytest.mark.asyncio
async def test_install_rejects_duplicate_id() -> None:
    example = _example_skill_dir()
    if not (example / "skill.json").is_file():
        pytest.skip("examples/skill_echo 不存在")
    with tempfile.TemporaryDirectory() as td:
        skills_root = Path(td) / "skills"
        await install_skill_source(skills_root, str(example.resolve()))
        with pytest.raises(FileExistsError):
            await install_skill_source(skills_root, str(example.resolve()))


@pytest.mark.asyncio
async def test_load_skill_factory_imports_sibling_module() -> None:
    """build_tools 内再 import 同目录模块时，skill 目录须仍在 sys.path（回归 #loader）。"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "multi_file_skill"
        root.mkdir(parents=True)
        (root / "skill.json").write_text(
            '{"id":"multi_file_skill","module":"main","factory":"build_tools"}\n',
            encoding="utf-8",
        )
        (root / "helper.py").write_text(
            "from kip.tools.base import BaseTool\n"
            "class H(BaseTool):\n"
            "    name = 'h'\n"
            "    description = 'x'\n"
            "    is_safe = True\n"
            "    @property\n"
            "    def schema(self):\n"
            "        return {'type':'object','properties':{}}\n"
            "    async def execute(self, args):\n"
            "        return 'ok'\n",
            encoding="utf-8",
        )
        (root / "main.py").write_text(
            "def build_tools(cwd):\n"
            "    import helper\n"
            "    return [helper.H()]\n",
            encoding="utf-8",
        )
        tools = load_tools_from_skill_dir(root, ".")
        assert len(tools) == 1
        assert tools[0].name == "multi_file_skill__h"
        out = await tools[0].execute({})
        assert out == "ok"
