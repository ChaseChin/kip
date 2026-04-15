"""YAML 配置加载与 Pydantic 校验。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class LLMConfig(BaseModel):
    """LLM API Key 仅从环境变量读取，变量名由 `api_key_env` 指定（默认 KIP_LLM_APIKEY）。"""

    model_config = ConfigDict(extra="ignore")

    model: str = "qwen3.6-plus"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key_env: str = Field(
        default="KIP_LLM_APIKEY",
        description="存放 API Key 的环境变量名；密钥本身请 export，勿写入 config.yaml。",
    )
    max_output_tokens: int = 4096
    temperature: float = 0.7
    context_window: int | None = Field(
        default=65536,
        description="上下文窗口提示（展示/约束）；百炼 Qwen3 长文本常用约 64k～256k token，默认 65536。",
    )


class MemoryConfig(BaseModel):
    # 相对配置根或绝对路径（配置根见 kip.paths）
    db_path: str = "data/kip_memory.db"
    max_history_messages: int = 40
    # 长期记忆：写入 memories 表（session_id 为空表示跨会话）；提取为额外 LLM 调用，已在后台执行不阻塞主回复
    auto_extract_long_term: bool = True
    # 注入到 system prompt 的条数上限；0 表示不注入（仍会按 auto_extract 写入）
    long_term_inject_max: int = 12
    # 单文件送入模型的最大字符数（超出截断）
    dev_md_max_chars: int = 32000


class SafetyConfig(BaseModel):
    enabled: bool = True
    browser_allowed_hosts: list[str] = Field(default_factory=list)


class MCPConfig(BaseModel):
    servers: list[dict[str, Any]] = Field(default_factory=list)


class PathsConfig(BaseModel):
    cwd: str = "."
    # 动态 skill 安装目录（相对配置根或绝对路径；配置根见 kip.paths）
    skills_dir: str = "data/skills"
    # Agent 人设 / 规则 / 能力（Markdown），相对配置根或绝对路径；也可用环境变量 KIP_SOUL 覆盖
    soul_path: str = "SOUL.MD"
    # 开发记录 / 对话摘录（Markdown），相对配置根或绝对路径；也可用环境变量 KIP_DEV_MD 覆盖（与 soul_path 用法一致）
    dev_md_path: str = "DEV.MD"
    # 运行日志（轮转）；相对配置根或绝对路径；也可用环境变量 KIP_LOG_LEVEL=DEBUG 提高详细度
    log_path: str = "data/kip.log"
    log_level: str = "INFO"


class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)


def load_config(path: Path | None = None) -> AppConfig:
    """从 YAML 加载配置；文件不存在时返回默认值。

    加载后相对路径字段相对于本次使用的 `config.yaml` 所在目录解析；
    若文件不存在则相对 `get_kip_home()`（见 `kip.paths`）。
    """
    from kip.paths import default_config_file, set_config_root

    p = path if path is not None else default_config_file()
    p = p.expanduser().resolve()
    set_config_root(p.parent)
    if not p.is_file():
        return AppConfig()
    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    return AppConfig.model_validate(data)


def save_config(cfg: AppConfig, path: Path | None = None) -> None:
    """将配置写回 YAML。"""
    from kip.paths import default_config_file, set_config_root

    p = path if path is not None else default_config_file()
    p = p.expanduser().resolve()
    set_config_root(p.parent)
    p.parent.mkdir(parents=True, exist_ok=True)
    dump = cfg.model_dump(mode="json")
    p.write_text(yaml.safe_dump(dump, allow_unicode=True, sort_keys=False), encoding="utf-8")
