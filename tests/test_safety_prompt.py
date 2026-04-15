"""安全确认与 prompt_one_line（asyncio.to_thread + input）。"""

from __future__ import annotations

import pytest

from kip.safety import SafetyGate, prompt_one_line


@pytest.mark.asyncio
async def test_prompt_one_line_reads_via_input(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(msg: str = "") -> str:
        assert "ok?" in msg
        return "line"

    monkeypatch.setattr("builtins.input", _fake)
    assert await prompt_one_line("ok? ") == "line"


@pytest.mark.asyncio
async def test_confirm_accepts_y(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda msg="": "y")
    g = SafetyGate(enabled=True, yolo=False)
    assert await g.confirm("tool(x)") is True


@pytest.mark.asyncio
async def test_confirm_accepts_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda msg="": "yes")
    g = SafetyGate(enabled=True, yolo=False)
    assert await g.confirm("tool(x)") is True


@pytest.mark.asyncio
async def test_confirm_rejects_other(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda msg="": "n")
    g = SafetyGate(enabled=True, yolo=False)
    assert await g.confirm("tool(x)") is False


@pytest.mark.asyncio
async def test_confirm_skipped_when_yolo_non_destructive(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    def _no_input(msg: str = "") -> str:
        called.append(msg)
        return "n"

    monkeypatch.setattr("builtins.input", _no_input)
    g = SafetyGate(enabled=True, yolo=True)
    assert await g.confirm("read_file(x)") is True
    assert called == []
