"""pytest 根配置：将 src 加入 import 路径。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


import pytest


@pytest.fixture(autouse=True)
def _reset_kip_config_root() -> None:
    """避免用例间残留 `load_config` 写入的全局配置根。"""
    from kip.paths import reset_config_root

    reset_config_root()
    yield
    reset_config_root()
