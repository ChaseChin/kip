"""首次运行向导。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kip.config import AppConfig, load_config
from kip.first_run import _ensure_layout_and_default_files, default_config_missing, first_run_wizard
from kip.paths import reset_config_root


def test_default_config_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KIP_HOME", str(tmp_path))
    reset_config_root()
    assert default_config_missing() is True
    (tmp_path / "config.yaml").write_text("llm:\n  model: x\n", encoding="utf-8")
    reset_config_root()
    load_config()
    assert default_config_missing() is False


def test_ensure_layout_writes_soul_and_dev(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KIP_HOME", str(tmp_path))
    reset_config_root()
    cfg = AppConfig()
    from kip.paths import set_config_root

    set_config_root(tmp_path)
    _ensure_layout_and_default_files(cfg)
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "data" / "skills").is_dir()
    assert (tmp_path / "SOUL.MD").is_file()
    assert "KIP CLI" in (tmp_path / "SOUL.MD").read_text(encoding="utf-8")
    assert (tmp_path / "DEV.MD").is_file()
    assert (tmp_path / "README.txt").is_file()


def test_first_run_wizard_saves_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KIP_HOME", str(tmp_path))
    reset_config_root()
    cfg = AppConfig()
    from kip.paths import set_config_root

    set_config_root(tmp_path)
    inputs = iter(["", "", "sk-test-key"])  # Enter, Enter (keep model), key
    with patch("builtins.input", lambda _: next(inputs)):
        cfg = first_run_wizard(cfg)
    assert (tmp_path / "config.yaml").is_file()
    assert cfg.llm.model == "qwen3.6-plus"
    import os

    assert os.environ.get("KIP_LLM_APIKEY") == "sk-test-key"
