"""将 DEV.MD 经 LLM 提炼为全局长期记忆（dev_md_* key）。"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from kip.llm_client import LLMClient, parse_assistant_message
from kip.memory import MemoryStore
from kip.memory_extract import _KEY_RE, _parse_json_object, _sanitize_key

if TYPE_CHECKING:
    from kip.config import AppConfig

_log = logging.getLogger("kip.dev_md_ingest")

_MAX_ITEMS = 24
_MAX_VALUE_LEN = 500
_KEY_PREFIX = "dev_md_"
# 与 dev_md_* 内容条目区分，避免 delete_global_memories_key_prefix 误删
_META_CONTENT_SHA_KEY = "kip_dev_md_content_sha256"

_DEV_MD_SYSTEM = (
    "你是项目知识提炼助手。输入为一份 DEV.MD（开发记录或对话导出）的全文或节选。\n"
    "请提炼为可长期复用的要点，供后续对话从「长期记忆」中召回。\n"
    "必须只输出一个 JSON 对象，格式："
    '{"items":[{"key":"英文小写蛇形标识","value":"一句简短事实"}]}。\n'
    "要求：\n"
    "- 收录技术决策、约定、目录/文件、已实现能力、待办、已知问题；忽略寒暄与重复赘述。\n"
    "- key 短且稳定；value 一条不超过约 120 字中文。\n"
    f"- 最多 {_MAX_ITEMS} 条；无可提炼内容输出 {{\"items\":[]}}。\n"
    "不要 markdown，不要解释。"
)


async def ingest_dev_md_to_global_memory(
    llm: LLMClient,
    mem: MemoryStore,
    cfg: "AppConfig",
    dev_md_path: Path,
    *,
    force: bool = False,
) -> tuple[int, str]:
    """
    读取 DEV.MD，经 LLM 写入全局记忆（先删除旧 dev_md_*，再插入新条目）。
    若全文 SHA256 与上次成功写入时一致且非 force，则跳过 LLM 与写入，避免重复。
    返回 (写入条数, 人类可读说明)。
    """
    if not dev_md_path.is_file():
        return 0, "未找到 DEV.MD，已跳过。"

    try:
        raw_full = dev_md_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as e:
        _log.warning("dev_md_read_failed path=%s err=%s", dev_md_path, e)
        return 0, f"读取 DEV.MD 失败: {e}"

    if not raw_full:
        return 0, "DEV.MD 为空，已跳过。"

    content_sha = hashlib.sha256(raw_full.encode("utf-8")).hexdigest()
    if not force:
        last = await mem.get_global_memory_value(_META_CONTENT_SHA_KEY)
        if last == content_sha:
            return (
                0,
                "DEV.MD 内容与上次成功导入一致（SHA256 相同），已跳过，避免重复写入数据库。",
            )

    max_c = cfg.memory.dev_md_max_chars
    truncated = len(raw_full) > max_c
    raw = raw_full[:max_c] if truncated else raw_full

    user_block = f"文件路径: {dev_md_path}\n\n{raw}"
    if truncated:
        user_block += f"\n\n[系统注：原文已截断至前 {max_c} 字符]"

    resp = await llm.chat(
        [
            {"role": "system", "content": _DEV_MD_SYSTEM},
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
        _log.warning("dev_md_ingest_parse_empty content_preview=%s", (content or "")[:200])
        return 0, "未能从模型响应中解析出记忆条目（已跳过写入，保留原 dev_md 记忆）。"

    pending: list[tuple[str, str, dict[str, str]]] = []
    for raw_item in items[:_MAX_ITEMS]:
        if not isinstance(raw_item, dict):
            continue
        rk = raw_item.get("key")
        rv = raw_item.get("value")
        if not isinstance(rk, str) or not isinstance(rv, str):
            continue
        suffix = _sanitize_key(rk)
        if not suffix or not _KEY_RE.match(suffix):
            suffix = _sanitize_key("item_" + rk[:32])
        if not suffix or not _KEY_RE.match(suffix):
            continue
        full_key = f"{_KEY_PREFIX}{suffix}"
        if len(full_key) > 64:
            full_key = full_key[:64]
        val = rv.strip()
        if not val:
            continue
        if len(val) > _MAX_VALUE_LEN:
            val = val[: _MAX_VALUE_LEN - 1] + "…"
        pl = {"source": "dev_md", "path": str(dev_md_path)}
        pending.append((full_key, val, pl))

    if not pending:
        return 0, "DEV.MD 已分析，但未产生可写入的记忆条目（保留原 dev_md 记忆）。"

    await mem.delete_global_memories_key_prefix(_KEY_PREFIX)
    written = 0
    for full_key, val, pl in pending:
        await mem.upsert_global_memory(full_key, val, payload=pl)
        written += 1

    await mem.upsert_global_memory(
        _META_CONTENT_SHA_KEY,
        content_sha,
        payload={"path": str(dev_md_path), "algo": "sha256"},
    )

    return written, f"已从 DEV.MD 提炼并写入 {written} 条长期记忆（前缀 dev_md_），后续对话将自动注入上下文。"
