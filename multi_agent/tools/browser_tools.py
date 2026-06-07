"""
Browser tools backed by Playwright.

A single Playwright browser session is kept alive at module level so
multi-step interactions (navigate → click → type → read) share the same
page across tool calls within one agent.run() session.

Prerequisites
-------------
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import atexit

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Browser session singleton
# ---------------------------------------------------------------------------

_playwright = None
_browser    = None
_page       = None


def _get_page():
    """Return the shared page, starting Playwright on first call."""
    global _playwright, _browser, _page

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    if _playwright is None:
        _playwright = sync_playwright().start()

    if _browser is None or not _browser.is_connected():
        _browser = _playwright.chromium.launch(headless=True)
        _page    = _browser.new_page()
    elif _page is None or _page.is_closed():
        _page = _browser.new_page()

    return _page


def _cleanup() -> None:
    global _playwright, _browser, _page
    try:
        if _page and not _page.is_closed():
            _page.close()
        if _browser:
            _browser.close()
        if _playwright:
            _playwright.stop()
    except Exception:
        pass


atexit.register(_cleanup)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def browser_navigate(url: str) -> str:
    """Navigate to a URL and return the page title plus visible text (up to 4 000 chars)."""
    page = _get_page()
    try:
        page.goto(url, timeout=30_000)
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
        title   = page.title()
        content = page.inner_text("body")[:4_000]
        return f"[Page: {title}]\nURL: {page.url}\n\n{content}"
    except Exception as exc:
        return f"[error] navigate failed: {exc}"


@tool
def browser_click(selector: str) -> str:
    """Click an element on the current page. selector is a CSS selector or `text='...'`."""
    page = _get_page()
    try:
        page.click(selector, timeout=10_000)
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
        return f"[ok] clicked '{selector}'. Current URL: {page.url}"
    except Exception as exc:
        return f"[error] click failed: {exc}"


@tool
def browser_type(selector: str, text: str) -> str:
    """Clear a form field and type text into it. selector is a CSS selector."""
    page = _get_page()
    try:
        page.fill(selector, text, timeout=10_000)
        return f"[ok] typed into '{selector}'"
    except Exception as exc:
        return f"[error] type failed: {exc}"


@tool
def browser_get_content() -> str:
    """Return the visible text of the current page (up to 4 000 chars)."""
    page = _get_page()
    try:
        content = page.inner_text("body")
        return content[:4_000] if content else "[empty page]"
    except Exception as exc:
        return f"[error] get_content failed: {exc}"


@tool
def browser_extract_links() -> list[dict]:
    """Extract all hyperlinks from the current page as a list of {text, href} dicts (max 50)."""
    page = _get_page()
    try:
        anchors = page.query_selector_all("a[href]")
        links   = []
        for a in anchors[:50]:
            href = a.get_attribute("href") or ""
            text = (a.inner_text() or "").strip()
            if href.startswith("http"):
                links.append({"text": text, "href": href})
        return links
    except Exception as exc:
        return [{"error": str(exc)}]


@tool
def browser_scroll(direction: str = "down") -> str:
    """Scroll the current page. direction must be 'up' or 'down'."""
    page = _get_page()
    try:
        delta = 600 if direction == "down" else -600
        page.mouse.wheel(0, delta)
        return f"[ok] scrolled {direction}"
    except Exception as exc:
        return f"[error] scroll failed: {exc}"


@tool
def browser_go_back() -> str:
    """Navigate back to the previous page in browser history."""
    page = _get_page()
    try:
        page.go_back(timeout=10_000)
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
        return f"[ok] went back. Current URL: {page.url}"
    except Exception as exc:
        return f"[error] go_back failed: {exc}"


@tool
def browser_current_url() -> str:
    """Return the URL of the page currently loaded in the browser."""
    page = _get_page()
    try:
        return page.url
    except Exception as exc:
        return f"[error] {exc}"


tools: list = [
    browser_navigate,
    browser_click,
    browser_type,
    browser_get_content,
    browser_extract_links,
    browser_scroll,
    browser_go_back,
    browser_current_url,
]
