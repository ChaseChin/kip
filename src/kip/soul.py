"""SOUL.MD：Agent 人设、规则与能力（启动时读入）。"""

from __future__ import annotations

import os
from pathlib import Path

from kip.config import AppConfig
from kip.paths import resolve_config_relative

_MAX_SOUL_CHARS = 100_000


def resolve_soul_path(cfg: AppConfig) -> Path:
    """解析 SOUL 文件路径：环境变量 KIP_SOUL 优先，否则为配置 paths.soul_path（相对配置根）。"""
    env = os.environ.get("KIP_SOUL", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return resolve_config_relative(cfg.paths.soul_path)


def load_soul_markdown(cfg: AppConfig) -> tuple[str, Path]:
    """
    读取 SOUL 正文；文件不存在时返回 ("", path)。
    超长文本截断，避免撑爆上下文。
    """
    path = resolve_soul_path(cfg)
    if not path.is_file():
        return "", path
    raw = path.read_text(encoding="utf-8")
    # 去 BOM
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    text = raw.strip()
    if len(text) > _MAX_SOUL_CHARS:
        text = text[:_MAX_SOUL_CHARS] + "\n\n...(SOUL 过长已截断)"
    return text, path
