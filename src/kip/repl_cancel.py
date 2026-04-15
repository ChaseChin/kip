"""在长时间异步任务运行期间监听 Esc，取消任务并给出提示（Unix / Windows）。"""

from __future__ import annotations

import asyncio
import logging
import os
import select
import sys
import threading
from typing import Any, Coroutine, TypeVar

from rich.console import Console

T = TypeVar("T")

_log = logging.getLogger("kip.repl_cancel")

_CANCEL_MSG = "[yellow]已取消当前操作（Esc）。[/yellow]"


def _drain_available(fd: int) -> None:
    while True:
        if not select.select([fd], [], [], 0)[0]:
            break
        try:
            os.read(fd, 4096)
        except OSError:
            break


async def await_with_esc_cancel(
    coro: Coroutine[Any, Any, T],
    *,
    console: Console,
    cancel_message: str = _CANCEL_MSG,
) -> T:
    """运行协程；若在运行期间按下单独 Esc，则取消任务并抛出 asyncio.CancelledError。"""
    if sys.platform == "win32":
        return await _await_with_esc_cancel_windows(coro, console=console, cancel_message=cancel_message)
    return await _await_with_esc_cancel_unix(coro, console=console, cancel_message=cancel_message)


async def _await_with_esc_cancel_unix(
    coro: Coroutine[Any, Any, T],
    *,
    console: Console,
    cancel_message: str,
) -> T:
    import termios
    import tty

    loop = asyncio.get_running_loop()
    task: asyncio.Task[T] = asyncio.create_task(coro)
    stop = threading.Event()

    fd = sys.stdin.fileno()
    if not os.isatty(fd):
        return await task

    def worker() -> None:
        while not stop.is_set() and not task.done():
            try:
                r, _, _ = select.select([fd], [], [], 0.12)
            except (ValueError, OSError):
                break
            if not r or stop.is_set():
                continue
            try:
                b = os.read(fd, 1)
            except OSError:
                break
            if b != b"\x1b":
                continue
            # 短等：若还有后续字节则为方向键/功能键序列，排空并忽略
            try:
                if select.select([fd], [], [], 0.04)[0]:
                    _drain_available(fd)
                    continue
            except OSError:
                pass
            if task.done() or stop.is_set():
                continue

            def _cancel() -> None:
                if not task.done():
                    _log.info("esc_cancel_unix")
                    task.cancel()

            loop.call_soon_threadsafe(_cancel)

    old: list[Any] | None = None
    try:
        old = termios.tcgetattr(fd)
    except (termios.error, OSError):
        return await task

    t: threading.Thread | None = None
    try:
        tty.setcbreak(fd)
        t = threading.Thread(target=worker, name="kip-esc-cancel", daemon=True)
        t.start()
        return await task
    except asyncio.CancelledError:
        console.print(cancel_message)
        raise
    finally:
        stop.set()
        if old is not None:
            try:
                # 清掉子进程/误触留在 stdin 的字节，避免 prompt_toolkit 读到的行规与缓冲异常
                termios.tcflush(fd, termios.TCIFLUSH)
            except (termios.error, OSError):
                pass
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except (termios.error, OSError):
                pass
        if t is not None:
            t.join(timeout=0.6)


async def _await_with_esc_cancel_windows(
    coro: Coroutine[Any, Any, T],
    *,
    console: Console,
    cancel_message: str,
) -> T:
    try:
        import msvcrt  # type: ignore[import-not-found]
    except ImportError:
        return await coro

    loop = asyncio.get_running_loop()
    task: asyncio.Task[T] = asyncio.create_task(coro)
    stop = threading.Event()

    def worker() -> None:
        while not stop.is_set() and not task.done():
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch == b"\x1b" and not task.done() and not stop.is_set():

                    def _cancel() -> None:
                        if not task.done():
                            _log.info("esc_cancel_windows")
                            task.cancel()

                    loop.call_soon_threadsafe(_cancel)
            else:
                stop.wait(0.08)

    t = threading.Thread(target=worker, name="kip-esc-cancel-win", daemon=True)
    t.start()
    try:
        return await task
    except asyncio.CancelledError:
        console.print(cancel_message)
        raise
    finally:
        stop.set()
        t.join(timeout=0.6)
