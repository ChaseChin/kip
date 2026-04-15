"""从 Git / HTTP(zip) / 本地目录安装 skill 到 skills_root/<manifest.id>/。"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import httpx

from kip.skills.manifest import read_manifest


def _ensure_skill_id(skill_id: str) -> str:
    sid = re.sub(r"[^a-z0-9_]+", "_", skill_id.lower().strip()).strip("_")
    if not sid or not sid[0].isalpha():
        raise ValueError("skill_id 须以小写字母开头，仅含小写字母、数字、下划线")
    return sid[:63]


def _find_skill_root(base: Path) -> Path:
    if (base / "skill.json").is_file():
        return base
    for c in sorted(base.iterdir()):
        if c.is_dir() and (c / "skill.json").is_file():
            return c
    raise FileNotFoundError("未找到 skill.json（请确认压缩包或仓库根目录包含 skill.json）")


async def _materialize_source(source: str, staging: Path) -> None:
    """将来源展开到 staging 目录（其下应能定位 skill.json）。staging 一般尚不存在。"""
    src = source.strip()
    p = Path(src).expanduser()

    if p.is_dir():
        shutil.copytree(p, staging, symlinks=False)
        return
    if p.is_file() and src.lower().endswith(".zip"):
        staging.mkdir(parents=True)
        with zipfile.ZipFile(p, "r") as zf:
            zf.extractall(staging)
        return
    if src.startswith("git@") or src.endswith(".git") or "github.com" in src or src.startswith("git+"):
        await asyncio.to_thread(_git_clone_shallow, src, staging)
        return
    if src.startswith("http://") or src.startswith("https://"):
        staging.mkdir(parents=True)
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            r = await client.get(src)
            r.raise_for_status()
            body = r.content
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            tf.write(body)
            zpath = Path(tf.name)
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                zf.extractall(staging)
        finally:
            zpath.unlink(missing_ok=True)
        return

    raise ValueError(
        "不支持的 source：请使用本地目录、本地 .zip、git URL 或 http(s) 指向的 zip"
    )


def _git_clone_shallow(url: str, dest: Path) -> None:
    parent = dest.parent
    name = dest.name
    subprocess.run(
        ["git", "clone", "--depth", "1", url, name],
        cwd=str(parent),
        check=True,
        capture_output=True,
        text=True,
    )


def _flatten_single_root(staging: Path) -> None:
    """若 staging 下仅有一个子目录且其中才有 skill.json，则把内容提升到 staging。"""
    if (staging / "skill.json").is_file():
        return
    subs = [c for c in staging.iterdir() if c.is_dir()]
    files = [c for c in staging.iterdir() if c.is_file()]
    if len(subs) == 1 and not files:
        inner = subs[0]
        for item in list(inner.iterdir()):
            shutil.move(str(item), str(staging / item.name))
        inner.rmdir()


async def install_skill_source(
    skills_root: Path,
    source: str,
    skill_id: str | None = None,
) -> Path:
    """
    安装到 skills_root/<manifest.id>/。
    skill_id 若提供则必须与 skill.json 中 id 一致（用于校验）。
    """
    skills_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        staging = Path(td) / "work"
        await _materialize_source(source, staging)
        _flatten_single_root(staging)
        root = _find_skill_root(staging)
        manifest = read_manifest(root / "skill.json")
        if skill_id is not None and _ensure_skill_id(skill_id) != manifest.id:
            raise ValueError(
                f"skill_id={skill_id!r} 与 skill.json 中 id={manifest.id!r} 不一致"
            )
        dest = skills_root / manifest.id
        if dest.exists():
            raise FileExistsError(
                f"已安装同名 skill: {dest}（请先删除该目录后再装）"
            )
        # 将 root 目录整体移到目标（保持目录名为 manifest.id）
        if root == staging:
            shutil.move(str(root), str(dest))
        else:
            shutil.move(str(root), str(dest))
    return dest
