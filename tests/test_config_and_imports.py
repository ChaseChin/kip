"""配置与包导入。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from kip.config import AppConfig, MemoryConfig, PathsConfig


def test_package_version() -> None:
    import kip

    assert isinstance(kip.__version__, str)
    assert len(kip.__version__) > 0


def test_cli_version_flag() -> None:
    import kip

    r = subprocess.run(
        [sys.executable, "-m", "kip.main", "--version"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    out = (r.stdout + r.stderr).strip()
    assert kip.__version__ in out
    assert "kip" in out.lower()


def test_app_config_defaults() -> None:
    cfg = AppConfig()
    assert cfg.llm.model
    assert cfg.memory.db_path
    assert cfg.paths.skills_dir == "data/skills"
    assert cfg.memory.auto_extract_long_term is True


def test_memory_config_long_term_flags() -> None:
    m = MemoryConfig(long_term_inject_max=0, auto_extract_long_term=False)
    assert m.long_term_inject_max == 0
    assert m.auto_extract_long_term is False


def test_paths_config_skills_dir() -> None:
    p = PathsConfig(skills_dir="custom/skills")
    assert p.skills_dir == "custom/skills"


@pytest.mark.parametrize(
    "line,expect_cmd,expect_rest",
    [
        ("", "", ""),
        ("hello", "", "hello"),
        ("/help", "help", ""),
        ("/memory kw", "memory", "kw"),
        ("/model  qwen", "model", "qwen"),
    ],
)
def test_parse_slash(line: str, expect_cmd: str, expect_rest: str) -> None:
    from kip.repl_common import parse_slash

    cmd, rest = parse_slash(line)
    assert cmd == expect_cmd
    assert rest == expect_rest
