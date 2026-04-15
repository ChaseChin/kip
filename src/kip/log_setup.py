"""文件日志：便于排查 REPL / 工具 / TTY 等问题。"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from kip.config import AppConfig
from kip.paths import resolve_config_relative


def resolve_log_path(cfg: AppConfig) -> Path:
    return resolve_config_relative(cfg.paths.log_path)


def _parse_level(name: str) -> int:
    return getattr(logging, name.upper(), logging.INFO) if hasattr(logging, name.upper()) else logging.INFO


def reset_kip_logging_handlers() -> None:
    """移除 `kip` 日志器的文件 handler，便于 `/setup` 等场景更换日志路径后重新 setup_logging。"""
    log = logging.getLogger("kip")
    for h in list(log.handlers):
        try:
            h.close()
        except OSError:
            pass
        log.removeHandler(h)


def setup_logging(cfg: AppConfig) -> Path:
    """初始化 `kip` 日志器：轮转文件、UTF-8。可重复调用（仅首次生效）。"""
    log = logging.getLogger("kip")
    if log.handlers:
        return resolve_log_path(cfg)

    path = resolve_log_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)

    level_name = os.environ.get("KIP_LOG_LEVEL", cfg.paths.log_level).strip()
    level = _parse_level(level_name)

    h = RotatingFileHandler(
        path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    h.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(h)
    log.setLevel(level)

    for noisy in ("httpx", "httpcore", "httpcore.http11", "litellm", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    log.info("logging_init path=%s level=%s", path, logging.getLevelName(level))
    return path


def preview_text(text: str, max_len: int = 160) -> str:
    """日志用短预览（换行压成空格，避免撑爆文件）。"""
    s = " ".join(text.split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"
