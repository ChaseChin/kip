"""skill.json 清单校验。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SkillManifest(BaseModel):
    """与 skill 目录内 skill.json 对应。"""

    id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]{0,62}$",
        description="目录名与工具名前缀，仅小写蛇形",
    )
    name: str = ""
    version: str = "1.0.0"
    module: str = Field(..., description="同目录下 Python 文件名（不含 .py）")
    factory: str = "build_tools"


def read_manifest(path: Path) -> SkillManifest:
    raw = path.read_text(encoding="utf-8")
    data: Any = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("skill.json 必须是 JSON 对象")
    return SkillManifest.model_validate(data)
