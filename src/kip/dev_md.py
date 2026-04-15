"""将 REPL 本轮对话追加写入 DEV.MD（增量，与 Cursor 导出块格式一致）。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kip.config import AppConfig

from kip.paths import resolve_config_relative

_log = logging.getLogger("kip.dev_md")


def resolve_dev_md_path(cfg: "AppConfig") -> Path:
    """解析 DEV.MD 路径：环境变量 KIP_DEV_MD 优先，否则为配置 paths.dev_md_path（相对配置根，与 SOUL 一致）。"""
    env = os.environ.get("KIP_DEV_MD", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return resolve_config_relative(cfg.paths.dev_md_path)


def append_turn(user_text: str, assistant_text: str, *, dev_md: Path | None = None) -> None:
    """在 DEV.MD 末尾追加一轮 User / Cursor 块（与现有导出格式一致）。"""
    path = dev_md if dev_md is not None else resolve_config_relative("DEV.MD")
    block = f"""

---

**User**

{user_text}

---

**Cursor**

{assistant_text}

---
"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(block)
    except OSError as e:
        _log.warning("dev_md_append_failed path=%s err=%s", path, e)
