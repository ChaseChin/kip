"""kip.paths：配置根与用户目录。"""

from __future__ import annotations

from pathlib import Path

import pytest

from kip.config import AppConfig, load_config
from kip.paths import (
    default_config_file,
    get_config_root,
    get_kip_home,
    reset_config_root,
    resolve_config_relative,
)


def test_get_kip_home_respects_kip_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("KIP_HOME", str(tmp_path))
    assert get_kip_home() == tmp_path.resolve()


def test_default_config_file_under_kip_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KIP_CONFIG", raising=False)
    monkeypatch.setenv("KIP_HOME", str(tmp_path))
    assert default_config_file() == tmp_path / "config.yaml"


def test_load_config_sets_config_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KIP_CONFIG", raising=False)
    cfg_path = tmp_path / "sub" / "config.yaml"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text("llm:\n  model: qwen-turbo\n", encoding="utf-8")
    monkeypatch.setenv("KIP_CONFIG", str(cfg_path))
    reset_config_root()
    load_config()
    assert get_config_root() == tmp_path / "sub"
    p = resolve_config_relative("data/x.db")
    assert p == (tmp_path / "sub" / "data" / "x.db").resolve()


def test_resolve_relative_without_load_uses_kip_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KIP_CONFIG", raising=False)
    monkeypatch.setenv("KIP_HOME", str(tmp_path))
    reset_config_root()
    p = resolve_config_relative("data/kip.log")
    assert p == (tmp_path / "data" / "kip.log").resolve()


def test_app_config_paths_comment_only() -> None:
    cfg = AppConfig()
    assert cfg.paths.skills_dir == "data/skills"
