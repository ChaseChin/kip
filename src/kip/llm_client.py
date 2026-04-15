"""litellm 异步封装：非流式与流式（含工具调用累积）。"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

from kip.config import LLMConfig

# 避免首次 import litellm 时向 GitHub 拉取 model cost 表（内网/代理失败会产生 WARNING）
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")


def resolve_litellm_model(model: str, base_url: str) -> str:
    """根据 base_url 为 litellm 推断 provider 前缀。"""
    if not base_url.strip():
        return model
    b = base_url.lower()
    if model.startswith(("openai/", "anthropic/", "azure/", "dashscope/")):
        return model
    if "dashscope" in b or "aliyuncs.com" in b:
        return f"openai/{model}"
    if "openai.com" in b or "api.openai" in b:
        return model if "/" in model else f"openai/{model}"
    # 其他 OpenAI 兼容接口
    return f"openai/{model}"


def _assert_latin1_http_field(value: str, what: str) -> None:
    """HTTP 头仅允许 latin-1；密钥、URL 若含中文或全角符号会在底层触发 UnicodeEncodeError。"""
    try:
        value.encode("latin-1")
    except UnicodeEncodeError as e:
        raise ValueError(
            f"{what} 含无法用于 HTTP 头的字符（请勿混入中文、全角符号或不可见字符）；"
            "请检查 API Key 与 `llm.base_url` 是否为纯 ASCII。"
        ) from e


class LLMClient:
    def __init__(self, cfg: LLMConfig) -> None:
        self._cfg = cfg
        self._model = resolve_litellm_model(cfg.model, cfg.base_url)

    @property
    def model_id(self) -> str:
        return self._model

    def _api_key(self) -> str:
        """密钥只来自环境变量 `api_key_env`（默认 KIP_LLM_APIKEY），不由 YAML 保存。"""
        return os.environ.get(self._cfg.api_key_env, "").strip()

    def _base_kwargs(self) -> dict[str, Any]:
        key = self._api_key()
        if key:
            _assert_latin1_http_field(key, f"环境变量 `{self._cfg.api_key_env}` 中的 API Key")
        base = self._cfg.base_url.strip()
        if base:
            _assert_latin1_http_field(base, "`config.yaml` 中的 `llm.base_url`")
        kw: dict[str, Any] = {
            "model": self._model,
            "api_key": key or None,
            "temperature": self._cfg.temperature,
            "max_tokens": self._cfg.max_output_tokens,
        }
        if base:
            kw["api_base"] = base
        return kw

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = "auto",
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """单次非流式完成，返回 litellm 响应 dict。"""
        import litellm

        kw = self._base_kwargs()
        if temperature is not None:
            kw["temperature"] = temperature
        kw["messages"] = messages
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = tool_choice
        resp = await litellm.acompletion(**kw)
        if hasattr(resp, "model_dump"):
            return resp.model_dump()  # type: ignore[no-any-return]
        return dict(resp)  # type: ignore[arg-type]

    async def chat_stream_text(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """流式输出 assistant 文本片段（无工具时使用）。"""
        import litellm

        kw = self._base_kwargs()
        kw["messages"] = messages
        kw["stream"] = True
        if tools:
            kw["tools"] = tools
        stream = await litellm.acompletion(**kw)
        async for chunk in stream:  # type: ignore[assignment]
            ch = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk
            choices = ch.get("choices") or []
            if not choices:
                continue
            delta = (choices[0].get("delta") or {}) if isinstance(choices[0], dict) else {}
            if hasattr(choices[0], "delta"):
                d = choices[0].delta
                content = getattr(d, "content", None) if d else None
            else:
                content = delta.get("content")
            if content:
                yield content


def _msg_to_dict(msg: Any) -> dict[str, Any]:
    if isinstance(msg, dict):
        return msg
    if hasattr(msg, "model_dump"):
        return msg.model_dump()  # type: ignore[no-any-return]
    return dict(msg)  # type: ignore[arg-type]


def parse_assistant_message(resp: dict[str, Any]) -> dict[str, Any]:
    """从 acompletion 响应提取 assistant 消息。"""
    choices = resp.get("choices") or []
    if not choices:
        return {"role": "assistant", "content": ""}
    raw = choices[0].get("message")
    msg = _msg_to_dict(raw or {})
    role = msg.get("role", "assistant")
    content = msg.get("content")
    tool_calls = msg.get("tool_calls")
    out: dict[str, Any] = {"role": role, "content": content}
    if tool_calls:
        norm: list[Any] = []
        for tc in tool_calls:
            if hasattr(tc, "model_dump"):
                norm.append(tc.model_dump())
            elif isinstance(tc, dict):
                norm.append(tc)
            else:
                norm.append(dict(tc))  # type: ignore[arg-type]
        out["tool_calls"] = norm
    return out


def repair_json_args(raw: str) -> dict[str, Any]:
    """尝试修复非严格 JSON 的工具参数（如 key=value）。"""
    raw = raw.strip()
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        pass
    # key=value 简易解析
    parts: dict[str, str] = {}
    for segment in raw.split(","):
        segment = segment.strip()
        if "=" in segment:
            k, val = segment.split("=", 1)
            parts[k.strip()] = val.strip().strip('"').strip("'")
    return parts
