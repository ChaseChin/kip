"""install_skill / list_skills：安装并注册动态 skill 工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from kip.skills.install import install_skill_source
from kip.skills.loader import load_tools_from_skill_dir
from kip.skills.manifest import read_manifest
from kip.tools.base import BaseTool


class InstallSkillTool(BaseTool):
    """从本地路径、git、http(s) zip 安装 skill，并立即注册其工具。"""

    name = "install_skill"
    description = (
        "安装一个 KIP skill 包到本地 skills 目录。"
        "source 可为：本地文件夹路径、本地 .zip、git clone 地址、或 http(s) 指向的 zip。"
        "安装成功后，该 skill 提供的工具会立刻可用（工具名带 skill_id__ 前缀）。"
    )
    is_safe = False

    def __init__(
        self,
        skills_root: Path,
        cwd: str,
        on_installed: Callable[[list[BaseTool]], None],
    ) -> None:
        self._skills_root = skills_root
        self._cwd = cwd
        self._on_installed = on_installed

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "本地目录、.zip 路径、git URL 或 zip 的 https 链接",
                },
                "skill_id": {
                    "type": "string",
                    "description": "可选，必须与 skill.json 中 id 一致，仅作校验",
                },
            },
            "required": ["source"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        source = str(args.get("source") or "").strip()
        if not source:
            return "错误: 需要参数 source"
        sid_raw = args.get("skill_id")
        skill_id = str(sid_raw).strip() if sid_raw else None
        if skill_id == "":
            skill_id = None
        try:
            dest = await install_skill_source(self._skills_root, source, skill_id)
        except Exception as e:
            return f"安装失败: {e}"
        try:
            new_tools = load_tools_from_skill_dir(dest, self._cwd)
        except Exception as e:
            return f"已下载到 {dest}，但加载工具失败: {e}（可检查 skill.json 与 Python 模块）"
        if not new_tools:
            return f"已安装到 {dest}，但未导出任何工具（检查 factory 返回值）。"
        self._on_installed(new_tools)
        names = ", ".join(t.name for t in new_tools)
        return f"安装成功: {dest.name}。已注册工具: {names}"


class ListSkillsTool(BaseTool):
    """列出 skills 目录下已安装的 skill（读 skill.json）。"""

    name = "list_skills"
    description = "列出本机已安装的 KIP skill 名称、版本与 id（不加载 Python 模块）。"
    is_safe = True

    def __init__(self, skills_root: Path) -> None:
        self._skills_root = skills_root

    @property
    def schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, args: dict[str, Any]) -> str:
        root = self._skills_root
        if not root.is_dir():
            return "尚未创建 skills 目录，暂无已安装 skill。"
        lines: list[str] = []
        for p in sorted(root.iterdir()):
            if not p.is_dir():
                continue
            mf = p / "skill.json"
            if not mf.is_file():
                continue
            try:
                m = read_manifest(mf)
                lines.append(f"- {m.id} ({m.name}) v{m.version}")
            except Exception as e:
                lines.append(f"- {p.name} (读取失败: {e})")
        if not lines:
            return f"{root} 下暂无有效 skill（需含 skill.json）。"
        return "已安装 skill:\n" + "\n".join(lines)
