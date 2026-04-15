"""从单轮对话中提取长期记忆并写入 SQLite（全局 key）。"""

from __future__ import annotations

import json
import re
from typing import Any

from kip.config import MemoryConfig
from kip.llm_client import LLMClient, parse_assistant_message
from kip.memory import MemoryStore

_MAX_USER = 6000
_MAX_ASSIST = 6000
_MAX_VALUE_LEN = 500
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

_EXTRACTION_SYSTEM = (
    "你是记忆归档助手。根据「用户输入」与「助手回复」，提取值得长期保存的事实。"
    "只收录稳定信息：用户身份/称呼、偏好与习惯、长期项目、技术约定等；"
    "忽略一次性任务、临时数字、寒暄。"
    "必须只输出一个 JSON 对象，格式："
    '{"items":[{"key":"英文小写蛇形标识","value":"一句简短事实"}]}。'
    "最多 5 条；若无值得保存的内容输出 {\"items\":[]}。不要 markdown，不要解释。"
)


def _parse_json_object(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        obj = json.loads(text[start : end + 1])
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def _sanitize_key(raw: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", raw.lower().strip())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return ""
    if s[0].isdigit():
        s = "k_" + s
    return s[:64]


async def maybe_extract_long_term_memories(
    llm: LLMClient,
    mem: MemoryStore,
    cfg: MemoryConfig,
    user_text: str,
    assistant_text: str,
) -> None:
    if not cfg.auto_extract_long_term:
        return
    at = assistant_text.strip()
    if not at:
        return

    ut = user_text[:_MAX_USER]
    at = at[:_MAX_ASSIST]

    existing = await mem.list_global_memories_latest(limit=40)
    existing_lines = "\n".join(f"- {k}: {v}" for k, v in existing) or "(尚无)"

    user_block = (
        f"已有全局长期记忆（可更新 value，key 尽量复用）：\n{existing_lines}\n\n"
        f"---\n用户说：\n{ut}\n\n助手答：\n{at}"
    )

    resp = await llm.chat(
        [
            {"role": "system", "content": _EXTRACTION_SYSTEM},
            {"role": "user", "content": user_block},
        ],
        tools=None,
        temperature=0.2,
    )
    asst = parse_assistant_message(resp)
    content = asst.get("content") or ""
    data = _parse_json_object(str(content))
    items = data.get("items")
    if not isinstance(items, list):
        return

    for raw in items[:5]:
        if not isinstance(raw, dict):
            continue
        rk = raw.get("key")
        rv = raw.get("value")
        if not isinstance(rk, str) or not isinstance(rv, str):
            continue
        key = _sanitize_key(rk)
        if not key or not _KEY_RE.match(key):
            key = _sanitize_key("fact_" + rk[:40])
        if not key or not _KEY_RE.match(key):
            continue
        val = rv.strip()
        if not val:
            continue
        if len(val) > _MAX_VALUE_LEN:
            val = val[: _MAX_VALUE_LEN - 1] + "…"
        await mem.upsert_global_memory(key, val, payload={"source": "llm_extract"})
