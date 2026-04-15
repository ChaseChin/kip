"""斜杠命令补全。"""

from __future__ import annotations

from prompt_toolkit.document import Document

from kip.repl_completer import SlashCommandCompleter


def _complete(text: str) -> list[str]:
    c = SlashCommandCompleter()
    doc = Document(text, len(text))
    return sorted({x.text for x in c.get_completions(doc, None)})


def test_completer_empty_prefix_lists_commands() -> None:
    out = _complete("/")
    assert "/help" in out
    assert "/setup" in out
    assert "/clear" in out


def test_completer_prefix_filters() -> None:
    out = _complete("/hel")
    assert out == ["/help"]


def test_completer_setup_subcommands() -> None:
    out = _complete("/setup ")
    assert "/setup all" in out
    assert "/setup force" in out
    out2 = _complete("/setup al")
    assert out2 == ["/setup all"]


def test_completer_safety_subcommands() -> None:
    out = _complete("/safety ")
    assert "/safety on" in out
    assert "/safety off" in out


def test_completer_ignores_non_slash_lines() -> None:
    c = SlashCommandCompleter()
    doc = Document("hello /", 7)
    assert list(c.get_completions(doc, None)) == []


def test_completer_ignores_multiline() -> None:
    c = SlashCommandCompleter()
    doc = Document("/help\n", 6)
    assert list(c.get_completions(doc, None)) == []
