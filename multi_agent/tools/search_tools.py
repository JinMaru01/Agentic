"""
Search tools for the Search Engine Agent.

Uses duckduckgo-search (no API key required) for web and news queries.
Delegates full-page rendering to the shared Playwright browser session
so JavaScript-heavy articles are extracted correctly.

Prerequisites
-------------
    pip install duckduckgo-search playwright
    playwright install chromium
"""

from __future__ import annotations

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ddg_text(query: str, max_results: int = 8) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return [{"error": "duckduckgo-search not installed. Run: pip install duckduckgo-search"}]

    try:
        results = DDGS().text(query, max_results=max_results)
        return [{"title": r["title"], "url": r["href"], "snippet": r["body"]} for r in results]
    except Exception as exc:
        return [{"error": str(exc)}]


def _ddg_news(query: str, max_results: int = 10) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return [{"error": "duckduckgo-search not installed. Run: pip install duckduckgo-search"}]

    try:
        results = DDGS().news(query, max_results=max_results)
        return [
            {
                "title":   r.get("title", "") or "",
                "url":     r.get("url", "") or "",
                "snippet": r.get("body", "") or "",
                "source":  r.get("source", "") or "",
                "date":    r.get("date", "") or "",
            }
            for r in results
        ]
    except Exception as exc:
        return [{"error": str(exc)}]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_web(query: str) -> list[dict]:
    """
    Search the web for any topic using DuckDuckGo.
    Returns a list of {title, url, snippet} results.
    """
    return _ddg_text(query, max_results=8)


@tool
def search_ai_news() -> list[dict]:
    """
    Fetch the latest AI news: new models, research papers, product launches.
    Returns a list of {title, url, snippet, source, date} results.
    """
    return _ddg_news("artificial intelligence AI news latest 2025", max_results=10)


@tool
def search_ai_topic(topic: str) -> list[dict]:
    """
    Deep-search a specific AI topic, tool, model, or concept.
    Examples: 'Claude 4', 'GPT-5', 'LangGraph agentic RAG', 'diffusion models'.
    Returns a list of {title, url, snippet} results.
    """
    return _ddg_text(f"{topic} artificial intelligence AI", max_results=8)


@tool
def fetch_article(url: str) -> str:
    """
    Fetch and extract the readable text content of any web URL.
    Uses a real browser session so JavaScript-rendered pages work correctly.
    Returns the page title and up to 4 000 characters of visible text.
    """
    from .browser_tools import browser_navigate
    return browser_navigate.invoke({"url": url})


@tool
def browse_website(task: str) -> str:
    """
    Delegate a multi-step browsing task to the Browser Agent.
    Use this when a task requires navigation, clicking, form filling, or
    reading across multiple pages — not just a single URL fetch.
    task: plain-English description, e.g. 'Go to https://openai.com, find the latest blog post, and summarise it.'
    """
    from config import AgentConfig
    from ..agent.browser import BrowserAgent

    agent  = BrowserAgent(AgentConfig())
    result = agent.run(task)

    for msg in reversed(result.get("messages", [])):
        if type(msg).__name__ == "AIMessage" and msg.content:
            return msg.content

    return "[no response from browser agent]"


tools: list = [search_web, search_ai_news, search_ai_topic, fetch_article, browse_website]
