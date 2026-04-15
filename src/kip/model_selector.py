"""首次启动模型与 API Key 引导。"""

from __future__ import annotations

from typing import Any

from kip.config import AppConfig, LLMConfig, save_config
from kip.paths import default_config_file

_DEFAULT_KEY_ENV = "KIP_LLM_APIKEY"
_DASHSCOPE_COMPAT = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 预设：百炼 Qwen3 为主；OpenAI / DeepSeek 可选。每项可含 context_window 覆盖默认。
PRESETS: list[dict[str, Any]] = [
    {
        "label": "阿里云百炼 qwen3.6-plus",
        "model": "qwen3.6-plus",
        "base_url": _DASHSCOPE_COMPAT,
        "api_key_env": _DEFAULT_KEY_ENV,
        "context_window": 65536,
    },
    {
        "label": "阿里云百炼 qwen3.5-plus",
        "model": "qwen3.5-plus",
        "base_url": _DASHSCOPE_COMPAT,
        "api_key_env": _DEFAULT_KEY_ENV,
        "context_window": 65536,
    },
    {
        "label": "阿里云百炼 qwen3.5-flash",
        "model": "qwen3.5-flash",
        "base_url": _DASHSCOPE_COMPAT,
        "api_key_env": _DEFAULT_KEY_ENV,
        "context_window": 65536,
    },
    {"label": "OpenAI GPT-4o", "model": "gpt-4o", "base_url": "", "api_key_env": _DEFAULT_KEY_ENV, "context_window": 128000},
    {
        "label": "OpenAI GPT-3.5",
        "model": "gpt-3.5-turbo",
        "base_url": "",
        "api_key_env": _DEFAULT_KEY_ENV,
        "context_window": 16385,
    },
    {
        "label": "DeepSeek Chat",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": _DEFAULT_KEY_ENV,
        "context_window": 65536,
    },
]


def needs_setup(cfg: AppConfig) -> bool:
    """若 `llm.api_key_env` 指向的环境变量未设置或为空，则需要首次引导。"""
    import os

    key = os.environ.get(cfg.llm.api_key_env, "").strip()
    return not key


def apply_preset(cfg: AppConfig, index: int) -> AppConfig:
    if index < 0 or index >= len(PRESETS):
        return cfg
    p = PRESETS[index]
    cw = p.get("context_window", cfg.llm.context_window)
    cfg.llm = LLMConfig(
        model=str(p["model"]),
        base_url=str(p.get("base_url") or ""),
        api_key_env=str(p.get("api_key_env") or _DEFAULT_KEY_ENV),
        max_output_tokens=cfg.llm.max_output_tokens,
        temperature=cfg.llm.temperature,
        context_window=cw if cw is not None else cfg.llm.context_window,
    )
    return cfg


def apply_custom_model(cfg: AppConfig, model: str, base_url: str) -> AppConfig:
    """用户自填模型 id 与 OpenAI 兼容 base_url。"""
    bu = base_url.strip()
    cfg.llm = LLMConfig(
        model=model.strip(),
        base_url=bu,
        api_key_env=cfg.llm.api_key_env,
        max_output_tokens=cfg.llm.max_output_tokens,
        temperature=cfg.llm.temperature,
        context_window=cfg.llm.context_window,
    )
    return cfg


def prompt_model_preset_and_api_key(cfg: AppConfig) -> AppConfig:
    """交互：模型预设与 API Key（仅设置进程内环境变量，不落盘密钥）。"""
    import os

    env = cfg.llm.api_key_env
    print(f"当前已加载: model={cfg.llm.model!r}, base_url={cfg.llm.base_url or '(默认 OpenAI 官方)'}")
    print("模型预设（回车=保留当前；输入 **m**=自定义模型名与 base_url）:")
    for i, p in enumerate(PRESETS):
        label, model = str(p["label"]), str(p["model"])
        # label 已含模型 id 时不再重复「— model」
        if label.endswith(model):
            print(f"  [{i}] {label}")
        else:
            print(f"  [{i}] {label} — {model}")
    choice = input("序号 或 m (回车=保留当前): ").strip().lower()
    if choice == "m":
        mid = input("模型 id（如 qwen3.6-plus、gpt-4o）: ").strip()
        if mid:
            default_hint = _DASHSCOPE_COMPAT
            bu_in = input(f"OpenAI 兼容 base_url [回车={default_hint}]: ").strip() or default_hint
            cfg = apply_custom_model(cfg, mid, bu_in)
        else:
            print("未输入模型 id，已保留当前模型配置。")
    elif choice:
        try:
            idx = int(choice)
        except ValueError:
            idx = -1
        if 0 <= idx < len(PRESETS):
            cfg = apply_preset(cfg, idx)
        else:
            print("无效序号，已保留当前模型配置。")
    val = input(
        f"请输入 API Key（将仅设置当前进程的环境变量 {env}，不写入配置文件；留空则请自行 export {env}）: "
    ).strip()
    if val:
        os.environ[env] = val
    return cfg


def interactive_setup(cfg: AppConfig) -> AppConfig:
    """同步 stdin 引导（在 REPL 启动前调用）。

    若已从 config.yaml 加载过模型，直接回车可保留，不会被默认预设覆盖。
    API Key 仅写入当前进程的环境变量，不写入 YAML；持久化请自行 export `llm.api_key_env`（默认 KIP_LLM_APIKEY）。
    """
    env = cfg.llm.api_key_env
    print(f"未检测到环境变量 {env!r}（LLM API Key 请配置在该变量中，config.yaml 只保存变量名）。")
    cfg = prompt_model_preset_and_api_key(cfg)
    save_config(cfg)
    print("配置已保存。")
    return cfg


def repl_llm_reconfigure(cfg: AppConfig) -> AppConfig:
    """供 `/setup` 使用：与首次启动相同的模型预设与 API Key 交互（密钥仍只写入当前进程环境变量）。"""
    print()
    print("=" * 52)
    print("  重新配置 LLM（流程与首次启动相同）")
    print("=" * 52)
    print()
    print(
        "下面将引导你选择模型并输入 API Key；"
        "密钥仅写入当前进程的环境变量，不写入 config.yaml，持久化请在本机 export。"
    )
    print()
    cfg = prompt_model_preset_and_api_key(cfg)
    save_config(cfg)
    print()
    print("LLM 配置已保存。")
    print(f"如需调整更多模型或其它选项，可自行编辑配置文件：{default_config_file()}")
    return cfg
