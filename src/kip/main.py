"""程序入口：加载配置、初始化 Agent、启动 REPL。"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# 未 pip install 时允许直接运行：将 src 加入 path
_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from kip import __version__
from kip.cli import run_repl


def _try_utf8_stdio() -> None:
    """避免终端/管道默认编码为 latin-1 时打印中文或 Rich 输出报错。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass


def main() -> None:
    _try_utf8_stdio()
    # 须在任何 asyncio.run 之前设置，否则会打印「Executing Task… took … seconds」
    os.environ["PYTHONASYNCIODEBUG"] = "0"
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

    parser = argparse.ArgumentParser(prog="kip", description="KIP CLI Agent")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="打印版本号并退出",
    )
    parser.add_argument(
        "-y",
        "--yolo",
        action="store_true",
        help="YOLO 模式：跳过大部分安全确认（删除类操作除外）",
    )
    parser.add_argument(
        "-d",
        "--dev-md",
        action="store_true",
        help="启动时从配置的 paths.dev_md_path 提炼 DEV.MD 到长期记忆（文件未变化则跳过）",
    )
    parser.add_argument(
        "-t",
        "--trace",
        action="store_true",
        dest="trace_tools",
        help="终端显示工具调用详情（工具名与参数预览、步骤、成功时结果摘要）；默认不显示；失败时仍会打印错误",
    )
    args = parser.parse_args()
    # debug=False：关闭 asyncio 慢回调/任务调试输出（prompt 在 executor 里阻塞易误报）
    asyncio.run(
        run_repl(
            yolo=args.yolo,
            load_dev_md=args.dev_md,
            trace_tools=args.trace_tools,
        ),
        debug=False,
    )


if __name__ == "__main__":
    main()
