"""首次运行：创建配置目录、默认 SOUL/DEV、再引导模型与 API Key。"""

from __future__ import annotations

from kip.config import AppConfig
from kip.model_selector import prompt_model_preset_and_api_key

# 首次写入的示例 SOUL（用户可自由修改）
DEFAULT_SOUL_MD = """# KIP Agent · SOUL

> 本文件在启动时读入，合并到系统提示中的 **「人设与规则（SOUL）」**。可自由修改；支持 Markdown。
> 路径由 `config.yaml` 的 `paths.soul_path` 指定，也可用环境变量 `KIP_SOUL` 覆盖为其它文件。

## 人设

- 你是 **KIP CLI** 智能助手，冷静、清晰、有礼貌；以用户目标为先，优先用**工具**获取事实，避免臆测。
- 回复简洁，必要时使用 Markdown（列表、代码块、表格）。

## 规则

- 遵守安全门控：高风险操作需用户确认（YOLO 模式除外，删除类仍需谨慎）。
- 不编造工具返回结果；工具失败时如实说明。
- 不声称未提供的能力；内置工具（以当前环境实际加载为准）。

## 能力边界

- 可调用当前会话已注册的工具（文件、Shell、天气、浏览器、MCP、Skill、长期记忆等，以实际加载为准）。
- 无法访问未授权的网络、账号或本机未暴露的资源。
"""

DEFAULT_DEV_MD = """# DEV — 开发记录

> 由 KIP 首次运行创建。可在此记录与 IDE 协作的摘录；`/loaddev` 或 `kip -d` 可将内容提炼到长期记忆。

---
"""

DEFAULT_README_TXT = """KIP 配置目录说明
================

- config.yaml   主配置（可由首次运行向导生成）
- SOUL.MD       人设与规则（可编辑）
- DEV.MD        开发/协作摘录（可编辑）
- data/         数据库、日志、skills 等（路径可在 config.yaml 中调整）

环境变量提示：
  KIP_CONFIG    指定其它位置的 config.yaml
  KIP_HOME      指定用户级根目录（默认配置与相对路径锚点）
  KIP_LLM_APIKEY  LLM API 密钥（默认变量名，可在 config 中改 api_key_env）
"""


def default_config_missing() -> bool:
    """默认位置的 config.yaml 尚不存在时视为「首次运行」。"""
    from kip.paths import default_config_file

    return not default_config_file().is_file()


def _ensure_layout_and_default_files(cfg: AppConfig) -> None:
    """创建 data/、skills 根目录，并写入默认 SOUL/DEV（若不存在）。"""
    from kip.paths import get_config_root, resolve_config_relative

    root = get_config_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    skills = resolve_config_relative(cfg.paths.skills_dir)
    skills.mkdir(parents=True, exist_ok=True)

    soul = resolve_config_relative(cfg.paths.soul_path)
    if not soul.is_file():
        soul.parent.mkdir(parents=True, exist_ok=True)
        soul.write_text(DEFAULT_SOUL_MD.strip() + "\n", encoding="utf-8")

    dev = resolve_config_relative(cfg.paths.dev_md_path)
    if not dev.is_file():
        dev.parent.mkdir(parents=True, exist_ok=True)
        dev.write_text(DEFAULT_DEV_MD.strip() + "\n", encoding="utf-8")

    readme = root / "README.txt"
    if not readme.is_file():
        readme.write_text(DEFAULT_README_TXT.strip() + "\n", encoding="utf-8")


def first_run_wizard(cfg: AppConfig) -> AppConfig:
    """无 config.yaml 时调用：落盘目录与默认 Markdown，再交互选择模型并输入 API Key，最后 save_config。"""
    from kip.config import save_config
    from kip.paths import default_config_file

    print()
    print("=" * 52)
    print("  KIP 首次运行向导")
    print("=" * 52)
    print()
    print("将在配置目录中创建：")
    print("  • config.yaml（保存模型等设置）")
    print("  • SOUL.MD、DEV.MD（示例人设与开发记录，可编辑）")
    print("  • data/、skills 目录等")
    print()
    p = default_config_file()
    print(f"配置目录: {p.parent}")
    print()
    input("按 Enter 开始…")

    _ensure_layout_and_default_files(cfg)

    print()
    print("请完成模型与 API Key 设置（密钥仅写入当前进程的环境变量，持久化请在本机配置 export 或 shell 配置）。")
    print()
    cfg = prompt_model_preset_and_api_key(cfg)
    save_config(cfg)
    print()
    print(f"首次设置已完成。配置文件: {default_config_file()}")
    print("若需再次修改模型，可在 REPL 中使用 /model 或编辑 config.yaml。")
    print()
    return cfg
