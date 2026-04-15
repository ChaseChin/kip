"""K / I / P 终端像素字：█ 方块，矮扁比例 + 高饱和彩色。"""

from __future__ import annotations

from rich.text import Text

# 默认三色（rgb 高饱和，终端 Rich 可渲染）
STYLE_K = "bold rgb(56,189,248)"  # 天蓝
STYLE_I = "bold rgb(232,121,250)"  # 亮粉紫
STYLE_P = "bold rgb(250,204,21)"  # 金黄

# 与上面对应的 hex，供 prompt_toolkit 输入前缀着色（与欢迎像素字一致）
HEX_K = "#38bdf8"
HEX_I = "#e879fa"
HEX_P = "#facc15"


def kip_prompt_formatted_text() -> "FormattedText":
    """REPL 输入行前缀「K」「I」「P」三色 + 「 › 」默认色。"""
    from prompt_toolkit.formatted_text import FormattedText

    return FormattedText(
        [
            (f"fg:{HEX_K} bold", "K"),
            (f"fg:{HEX_I} bold", "I"),
            (f"fg:{HEX_P} bold", "P"),
            ("", " › "),
        ]
    )

# 每字母 5×5，略扁、总高度适中
_K: list[str] = [
    "█   █",
    "█  █ ",
    "███  ",
    "█  █ ",
    "█   █",
]
_I: list[str] = [
    " ███ ",
    "  █  ",
    "  █  ",
    "  █  ",
    " ███ ",
]
_P: list[str] = [
    "███  ",
    "█  █ ",
    "███  ",
    "█    ",
    "█    ",
]


def build_kip_pixel_text(
    k_style: str = STYLE_K,
    i_style: str = STYLE_I,
    p_style: str = STYLE_P,
    *,
    letter_gap: str = "  ",
) -> Text:
    """
    横向拼接 K、I、P；一格一 █，不再竖向复制、不再横向 ██ 加粗，避免过高、过宽。
    """
    wk, wi, wp = _K, _I, _P
    assert len(wk) == len(wi) == len(wp), "K/I/P 像素矩阵须同高"
    max_h = len(wk)

    out = Text()
    for row in range(max_h):
        if row > 0:
            out.append("\n")
        out.append(wk[row], style=k_style)
        out.append(letter_gap)
        out.append(wi[row], style=i_style)
        out.append(letter_gap)
        out.append(wp[row], style=p_style)
    return out
