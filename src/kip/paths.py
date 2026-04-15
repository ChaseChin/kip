"""KIP 数据与配置根路径：pip 安装后用用户目录，本地开发可用 KIP_HOME 指向仓库。"""

from __future__ import annotations

import os
from pathlib import Path

import platformdirs

_config_root: Path | None = None


def reset_config_root() -> None:
    """供测试在用例间恢复默认行为。"""
    global _config_root
    _config_root = None


def get_kip_home() -> Path:
    """用户级 KIP 根目录（数据、默认 config.yaml 所在目录）。

    优先级：环境变量 ``KIP_HOME`` > `platformdirs.user_data_dir("kip")`
    （Linux 多为 ``~/.local/share/kip``，macOS/Windows 为各平台惯例路径）。
    """
    env = os.environ.get("KIP_HOME", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(platformdirs.user_data_dir("kip", appauthor=False))


def get_config_root() -> Path:
    """解析配置中相对路径时的根目录：已加载的 `config.yaml` 所在目录，未加载时为 `get_kip_home()`。"""
    if _config_root is not None:
        return _config_root
    return get_kip_home()


def set_config_root(path: Path) -> None:
    """在加载或保存 `config.yaml` 后调用，将相对路径锚定到该文件所在目录。"""
    global _config_root
    _config_root = path.resolve()


def default_config_file() -> Path:
    """默认配置文件路径：``KIP_CONFIG`` 或 ``get_kip_home()/config.yaml``。"""
    env = os.environ.get("KIP_CONFIG", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return get_kip_home() / "config.yaml"


def resolve_config_relative(path_str: str) -> Path:
    """将配置项中的路径转为绝对路径：已是绝对路径则不变，否则相对 `get_config_root()`。"""
    p = Path(path_str).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (get_config_root() / p).resolve()
