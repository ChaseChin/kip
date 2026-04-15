"""Playwright 异步浏览器工具。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from kip.tools.base import BaseTool


class _BrowserCore:
    """懒加载共享浏览器实例。"""

    def __init__(self, allowed_hosts: list[str]) -> None:
        self._allowed_hosts = allowed_hosts
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._max_nav = 20
        self._nav_count = 0

    def _host_allowed(self, url: str) -> bool:
        if not self._allowed_hosts:
            return True
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            return False
        return any(host == h or host.endswith("." + h) for h in self._allowed_hosts)

    async def _ensure(self) -> Any:
        if self._page is not None:
            return self._page
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._page = await self._browser.new_page()
        return self._page

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None

    async def navigate(self, url: str) -> str:
        if self._nav_count >= self._max_nav:
            return "错误: 超过最大导航次数"
        self._nav_count += 1
        if not self._host_allowed(url):
            return f"错误: 域名不在白名单: {url}"
        page = await self._ensure()
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        return f"已打开 {url}"

    async def screenshot(self, path: str | None = None, full_page: bool = False) -> str:
        page = await self._ensure()
        p = path or "kip_screenshot.png"
        await page.screenshot(path=p, full_page=full_page)
        return f"截图已保存: {p}"

    async def extract(self, selector: str | None = None) -> str:
        page = await self._ensure()
        if selector:
            el = await page.query_selector(selector)
            if not el:
                return f"未找到元素: {selector}"
            text = await el.inner_text()
        else:
            text = await page.inner_text("body")
        return text[:12000] if text else ""

    async def click(self, selector: str) -> str:
        page = await self._ensure()
        await page.click(selector, timeout=30_000)
        return f"已点击 {selector}"

    async def fill(self, selector: str, text: str) -> str:
        page = await self._ensure()
        await page.fill(selector, text, timeout=30_000)
        return f"已填写 {selector}"


_core: _BrowserCore | None = None


def get_browser_core(allowed_hosts: list[str]) -> _BrowserCore:
    global _core
    if _core is None:
        _core = _BrowserCore(allowed_hosts)
    return _core


def reset_browser_core() -> None:
    global _core
    _core = None


class BrowserNavigateTool(BaseTool):
    name = "browser_navigate"
    description = "在浏览器中打开 URL（受域名白名单约束，空列表表示不限制）。"
    is_safe = False

    def __init__(self, allowed_hosts: list[str]) -> None:
        self._hosts = allowed_hosts

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "完整 http(s) URL"}},
            "required": ["url"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        core = get_browser_core(self._hosts)
        return await core.navigate(args["url"].strip())


class BrowserScreenshotTool(BaseTool):
    name = "browser_screenshot"
    description = "对当前页面截图保存到文件。"
    is_safe = True

    def __init__(self, allowed_hosts: list[str]) -> None:
        self._hosts = allowed_hosts

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "保存路径，可选"},
                "full_page": {"type": "boolean", "description": "是否整页截图"},
            },
        }

    async def execute(self, args: dict[str, Any]) -> str:
        core = get_browser_core(self._hosts)
        return await core.screenshot(
            args.get("path"),
            bool(args.get("full_page", False)),
        )


class BrowserExtractTool(BaseTool):
    name = "browser_extract"
    description = "提取当前页面文本；可选 CSS 选择器。"
    is_safe = True

    def __init__(self, allowed_hosts: list[str]) -> None:
        self._hosts = allowed_hosts

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"selector": {"type": "string", "description": "CSS 选择器，可选"}},
        }

    async def execute(self, args: dict[str, Any]) -> str:
        core = get_browser_core(self._hosts)
        sel = args.get("selector")
        return await core.extract(sel)


class BrowserClickTool(BaseTool):
    name = "browser_click"
    description = "点击当前页面上匹配 CSS 选择器的元素。"
    is_safe = False

    def __init__(self, allowed_hosts: list[str]) -> None:
        self._hosts = allowed_hosts

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"selector": {"type": "string", "description": "CSS 选择器"}},
            "required": ["selector"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        core = get_browser_core(self._hosts)
        return await core.click(args["selector"])


class BrowserFillTool(BaseTool):
    name = "browser_fill"
    description = "在输入框中填写文本。"
    is_safe = False

    def __init__(self, allowed_hosts: list[str]) -> None:
        self._hosts = allowed_hosts

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "输入框 CSS 选择器"},
                "text": {"type": "string", "description": "填写内容"},
            },
            "required": ["selector", "text"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        core = get_browser_core(self._hosts)
        return await core.fill(args["selector"], args["text"])
