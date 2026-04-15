"""异步 SQLite 记忆：会话、消息、工具日志、长期记忆。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from kip.paths import get_config_root

_log = logging.getLogger("kip.memory")

# 北京时间 UTC+8
TZ_CN = timezone(timedelta(hours=8))

# 仅内部元数据，不参与 list_global_memories_latest → system 注入
INTERNAL_GLOBAL_MEMORY_KEYS = frozenset({"kip_dev_md_content_sha256"})


def _now_iso() -> str:
    return datetime.now(TZ_CN).isoformat(timespec="seconds")


def _ensure_db_path(db_path: str) -> Path:
    p = Path(db_path).expanduser()
    if not p.is_absolute():
        p = get_config_root() / p
    p = p.resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


class MemoryStore:
    """连接池式异步 SQLite 封装。"""

    def __init__(self, db_path: str) -> None:
        self._path = _ensure_db_path(db_path)
        self._conn: aiosqlite.Connection | None = None

    @property
    def path(self) -> Path:
        return self._path

    async def connect(self) -> None:
        if self._conn is None:
            self._conn = await aiosqlite.connect(str(self._path))
            self._conn.row_factory = aiosqlite.Row
            await self._init_schema()
            _log.info("memory_connected path=%s", self._path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            _log.info("memory_closed path=%s", self._path)

    async def _init_schema(self) -> None:
        assert self._conn is not None
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload TEXT,
                status TEXT DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                tool_calls TEXT,
                tool_call_id TEXT,
                name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS tool_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                payload TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_tool_logs_session ON tool_logs(session_id);
            """
        )
        await self._conn.commit()

    async def create_session(self, session_id: str | None = None) -> str:
        assert self._conn is not None
        sid = session_id or str(uuid.uuid4())
        now = _now_iso()
        await self._conn.execute(
            "INSERT OR REPLACE INTO sessions (id, created_at, updated_at, payload, status) VALUES (?,?,?,?,?)",
            (sid, now, now, "{}", "active"),
        )
        await self._conn.commit()
        return sid

    async def touch_session(self, session_id: str) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (_now_iso(), session_id),
        )
        await self._conn.commit()

    async def append_message(self, session_id: str, msg: dict[str, Any]) -> None:
        assert self._conn is not None
        now = _now_iso()
        tool_calls = msg.get("tool_calls")
        tc_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
        await self._conn.execute(
            """
            INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, name, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                session_id,
                msg.get("role", "user"),
                msg.get("content"),
                tc_json,
                msg.get("tool_call_id"),
                msg.get("name"),
                now,
            ),
        )
        await self._conn.commit()

    async def load_recent_messages(
        self, session_id: str, limit: int
    ) -> list[dict[str, Any]]:
        assert self._conn is not None
        cur = await self._conn.execute(
            """
            SELECT role, content, tool_calls, tool_call_id, name FROM messages
            WHERE session_id = ? ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit),
        )
        rows = await cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in reversed(rows):
            m: dict[str, Any] = {"role": r["role"], "content": r["content"]}
            if r["tool_calls"]:
                m["tool_calls"] = json.loads(r["tool_calls"])
            if r["tool_call_id"]:
                m["tool_call_id"] = r["tool_call_id"]
            if r["name"]:
                m["name"] = r["name"]
            out.append(m)
        return out

    async def log_tool(
        self,
        session_id: str,
        tool_name: str,
        payload: dict[str, Any],
        status: str,
    ) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT INTO tool_logs (session_id, tool_name, payload, status, created_at)
            VALUES (?,?,?,?,?)
            """,
            (session_id, tool_name, json.dumps(payload, ensure_ascii=False), status, _now_iso()),
        )
        await self._conn.commit()

    async def add_memory(
        self,
        key: str,
        value: str,
        session_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        assert self._conn is not None
        pl = json.dumps(payload or {}, ensure_ascii=False)
        await self._conn.execute(
            """
            INSERT INTO memories (session_id, key, value, payload, created_at)
            VALUES (?,?,?,?,?)
            """,
            (session_id, key, value, pl, _now_iso()),
        )
        await self._conn.commit()

    async def list_global_memories_latest(self, limit: int = 40) -> list[tuple[str, str]]:
        """跨会话长期记忆：每个 key 只保留最新一条（按 id 最大）。"""
        assert self._conn is not None
        cur = await self._conn.execute(
            """
            SELECT key, value FROM memories
            WHERE session_id IS NULL
            ORDER BY id DESC
            """
        )
        rows = await cur.fetchall()
        seen: set[str] = set()
        out: list[tuple[str, str]] = []
        for r in rows:
            k = str(r["key"])
            if k in INTERNAL_GLOBAL_MEMORY_KEYS:
                continue
            if k in seen:
                continue
            seen.add(k)
            out.append((k, str(r["value"])))
            if len(out) >= limit:
                break
        return out

    async def upsert_global_memory(
        self,
        key: str,
        value: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """同一 key 只保留一条全局记忆（删除旧行再插入）。"""
        assert self._conn is not None
        pl = json.dumps(payload or {}, ensure_ascii=False)
        await self._conn.execute(
            "DELETE FROM memories WHERE session_id IS NULL AND key = ?",
            (key,),
        )
        await self._conn.execute(
            """
            INSERT INTO memories (session_id, key, value, payload, created_at)
            VALUES (?,?,?,?,?)
            """,
            (None, key, value, pl, _now_iso()),
        )
        await self._conn.commit()

    async def get_global_memory_value(self, key: str) -> str | None:
        """读取一条全局记忆（session_id IS NULL）的 value；不存在返回 None。"""
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT value FROM memories WHERE session_id IS NULL AND key = ? LIMIT 1",
            (key,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        v = row["value"]
        return str(v) if v is not None else None

    async def delete_global_memories_key_prefix(self, prefix: str) -> None:
        """删除全局记忆中 key 以 prefix 开头的行（用于 DEV.MD 重新导入前清空）。"""
        assert self._conn is not None
        await self._conn.execute(
            "DELETE FROM memories WHERE session_id IS NULL AND key LIKE ?",
            (f"{prefix}%",),
        )
        await self._conn.commit()

    async def search_memories(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        assert self._conn is not None
        like = f"%{keyword}%"
        cur = await self._conn.execute(
            """
            SELECT key, value, created_at FROM memories
            WHERE key LIKE ? OR value LIKE ? ORDER BY id DESC LIMIT ?
            """,
            (like, like, limit),
        )
        rows = await cur.fetchall()
        return [{"key": r["key"], "value": r["value"], "created_at": r["created_at"]} for r in rows]

    async def get_latest_session_id(self) -> str | None:
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
        )
        row = await cur.fetchone()
        return str(row["id"]) if row else None

    async def clear_session_messages(self, session_id: str) -> None:
        assert self._conn is not None
        await self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await self._conn.commit()

    async def get_exit_summary_stats(self, session_id: str) -> dict[str, int]:
        """退出时汇总：本会话消息/工具日志、长期与会话级记忆条数。"""
        assert self._conn is not None

        async def _one(sql: str, params: tuple[Any, ...] = ()) -> int:
            cur = await self._conn.execute(sql, params)
            row = await cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

        return {
            "messages_session": await _one(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (session_id,),
            ),
            "tool_logs_session": await _one(
                "SELECT COUNT(*) FROM tool_logs WHERE session_id = ?",
                (session_id,),
            ),
            "memories_long_global": await _one(
                "SELECT COUNT(*) FROM memories WHERE session_id IS NULL",
            ),
            "memories_session_scoped": await _one(
                "SELECT COUNT(*) FROM memories WHERE session_id = ?",
                (session_id,),
            ),
            "memories_total": await _one("SELECT COUNT(*) FROM memories"),
        }
