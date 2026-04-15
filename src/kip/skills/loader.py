"""从 skill 目录动态 import 并包装为带前缀的 BaseTool。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

from kip.skills.manifest import SkillManifest, read_manifest
from kip.tools.base import BaseTool


class SkillToolWrapper(BaseTool):
    """为 skill 内工具加全局唯一 name，避免与内置工具冲突。"""

    def __init__(self, inner: BaseTool, skill_id: str) -> None:
        self._inner = inner
        self.name = f"{skill_id}__{inner.name}"
        self.description = f"[skill:{skill_id}] {inner.description}"
        self.is_safe = inner.is_safe

    @property
    def schema(self) -> dict[str, Any]:
        return self._inner.schema

    async def execute(self, args: dict[str, Any]) -> str:
        return await self._inner.execute(args)


def _import_skill_main_module(skill_dir: Path, manifest: SkillManifest) -> Any:
    """在调用方已把 skill 目录加入 sys.path 的前提下，exec 主入口 .py。"""
    py = skill_dir / f"{manifest.module}.py"
    if not py.is_file():
        raise FileNotFoundError(f"缺少模块文件: {py.name}")
    # module 名须可作 Python 标识符片段；文件路径仍可为 manifest.module + ".py"
    safe_key = manifest.id.replace("-", "_")
    mod_name = f"kip_skill_{safe_key}_{manifest.module.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, py)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {py}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_tools_from_skill_dir(skill_dir: Path, cwd: str) -> list[BaseTool]:
    """读取 skill.json，调用 factory(cwd) -> list[BaseTool]，并加前缀包装。

    skill 目录必须在 **factory(cwd) 返回前** 保留在 sys.path 中，否则工厂函数内
    ``import`` 同目录下的其它模块（常见多文件 skill）会失败，导致启动时静默跳过该 skill。
    """
    manifest = read_manifest(skill_dir / "skill.json")
    if manifest.id != skill_dir.name:
        raise ValueError(
            f"skill.json 中 id={manifest.id!r} 与目录名 {skill_dir.name!r} 不一致"
        )
    skill_root = str(skill_dir.resolve())
    inserted = False
    if skill_root not in sys.path:
        sys.path.insert(0, skill_root)
        inserted = True
    try:
        mod = _import_skill_main_module(skill_dir, manifest)
        factory: Callable[[str], list[BaseTool]] = getattr(mod, manifest.factory)
        raw = factory(cwd)
    finally:
        if inserted and skill_root in sys.path:
            sys.path.remove(skill_root)
    if not isinstance(raw, list):
        raise TypeError(f"{manifest.factory}() 必须返回 list[BaseTool]")
    out: list[BaseTool] = []
    for t in raw:
        if not isinstance(t, BaseTool):
            raise TypeError("skill 工厂必须产出 BaseTool 实例")
        out.append(SkillToolWrapper(t, manifest.id))
    return out


def iter_skill_dirs(skills_root: Path) -> list[Path]:
    """列出 skills_root 下含 skill.json 的一级子目录。"""
    if not skills_root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(skills_root.iterdir()):
        if p.is_dir() and (p / "skill.json").is_file():
            out.append(p)
    return out


def load_installed_skill_tools_report(
    skills_root: Path, cwd: str
) -> tuple[list[BaseTool], list[str]]:
    """启动时加载全部 skill；单个失败时记录错误字符串，不阻塞启动。"""
    combined: list[BaseTool] = []
    errors: list[str] = []
    for d in iter_skill_dirs(skills_root):
        try:
            combined.extend(load_tools_from_skill_dir(d, cwd))
        except Exception as e:
            errors.append(f"{d.name}: {e}")
    return combined, errors


def load_installed_skill_tools(skills_root: Path, cwd: str) -> list[BaseTool]:
    tools, _ = load_installed_skill_tools_report(skills_root, cwd)
    return tools
