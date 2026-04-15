"""像素字 KIP。"""

from __future__ import annotations

from kip.pixel_kip import STYLE_K, build_kip_pixel_text


def test_build_kip_pixel_text_five_rows() -> None:
    t = build_kip_pixel_text()
    lines = str(t).split("\n")
    assert len(lines) == 5


def test_build_kip_pixel_text_uses_default_rgb_styles() -> None:
    t = build_kip_pixel_text()
    assert len(str(t)) > 20


def test_custom_styles_override() -> None:
    t = build_kip_pixel_text("red", "green", "blue")
    assert t is not None
    assert STYLE_K != "red"
