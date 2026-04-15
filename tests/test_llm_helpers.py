"""llm_client 辅助函数（无网络）。"""

from __future__ import annotations

from kip.llm_client import parse_assistant_message, repair_json_args


def test_repair_json_args_strict_json() -> None:
    assert repair_json_args('{"a": 1}') == {"a": 1}


def test_repair_json_args_key_value() -> None:
    out = repair_json_args("path=/tmp/foo,mode=w")
    assert out.get("path") == "/tmp/foo"
    assert out.get("mode") == "w"


def test_parse_assistant_message_empty_choices() -> None:
    msg = parse_assistant_message({"choices": []})
    assert msg.get("role") == "assistant"
    assert msg.get("content") == "" or msg.get("content") is None


def test_parse_assistant_message_with_content() -> None:
    msg = parse_assistant_message(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "hello",
                    }
                }
            ]
        }
    )
    assert msg["content"] == "hello"
