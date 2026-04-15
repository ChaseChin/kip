"""MemoryStore 异步行为。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kip.memory import MemoryStore


@pytest.mark.asyncio
async def test_session_messages_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "m.db"
        mem = MemoryStore(str(db))
        await mem.connect()
        sid = await mem.create_session()
        await mem.append_message(sid, {"role": "user", "content": "hi"})
        rows = await mem.load_recent_messages(sid, 10)
        assert len(rows) == 1
        assert rows[0]["role"] == "user"
        assert rows[0]["content"] == "hi"
        await mem.close()


@pytest.mark.asyncio
async def test_global_memory_upsert_and_list() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "m.db"
        mem = MemoryStore(str(db))
        await mem.connect()
        await mem.upsert_global_memory("pref_theme", "dark")
        await mem.upsert_global_memory("pref_theme", "light")
        latest = await mem.list_global_memories_latest(limit=10)
        assert any(k == "pref_theme" and v == "light" for k, v in latest)
        await mem.close()


@pytest.mark.asyncio
async def test_search_memories() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "m.db"
        mem = MemoryStore(str(db))
        await mem.connect()
        await mem.add_memory("note", "hello world", session_id=None)
        found = await mem.search_memories("hello", limit=5)
        assert len(found) >= 1
        await mem.close()
