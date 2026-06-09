AGENT_METADATA = {
    "auto": {
        "id":           "auto",
        "name":         "Auto (Orchestrator)",
        "description":  "Automatically selects the best agent for your request",
        "capabilities": ["Math calculations", "Mall & food ordering", "Web browsing", "AI news search", "Smart routing"],
        "icon":         "robot",
        "color":        "#6366f1",
    },
    "calculator": {
        "id":           "calculator",
        "name":         "Calculator",
        "description":  "Handles mathematical calculations and arithmetic",
        "capabilities": ["Addition / Subtraction", "Multiplication / Division", "Power & roots", "Percentages"],
        "icon":         "calculator",
        "color":        "#10b981",
    },
    "mall": {
        "id":           "mall",
        "name":         "Mall Assistant",
        "description":  "Browse stores, explore menus, and place orders",
        "capabilities": ["Store search", "Menu browsing", "Order placement", "Price lookup"],
        "icon":         "shopping",
        "color":        "#f59e0b",
    },
    "browser": {
        "id":           "browser",
        "name":         "Browser Agent",
        "description":  "Controls a real web browser to navigate sites and perform actions",
        "capabilities": ["Navigate URLs", "Click buttons & links", "Fill forms", "Extract page content", "Scroll & interact"],
        "icon":         "globe",
        "color":        "#3b82f6",
    },
    "search": {
        "id":           "search",
        "name":         "Search Agent",
        "description":  "Searches the internet for any question — AI news, general knowledge, or anything else",
        "capabilities": ["Latest AI news", "General web search", "Factual Q&A", "Article summarisation", "Universal fallback"],
        "icon":         "search",
        "color":        "#8b5cf6",
    },
    "credential": {
        "id":           "credential",
        "name":         "Credential Store",
        "description":  "Secure, policy-governed secret management — API keys, passwords, tokens, certificates",
        "capabilities": ["List secrets", "Retrieve via handle", "Rotate credentials", "Request approval", "Audit logging"],
        "icon":         "lock",
        "color":        "#dc2626",
    },
}

_SWITCH_REASONS: dict[tuple, str] = {
    ("calculator", "mall"):       "Your request seems to involve mall or store info — the Mall Assistant handles that better.",
    ("mall",       "calculator"): "Your request involves math — the Calculator agent handles that better.",
    ("browser",     "search"):      "Your request looks like a search query — the Search Agent handles that better.",
    ("search",      "browser"):     "Your request needs direct browser interaction — the Browser Agent handles that better.",
    ("calculator",  "credential"):  "Your request involves secret or credential management — the Credential Store handles that better.",
    ("search",      "credential"):  "Your request looks like a secret management task — the Credential Store handles that better.",
    ("credential",  "search"):      "Your request looks like a search query — the Search Agent handles that better.",
}


def get_suggestion_reason(forced_agent: str, suggested_agent: str) -> str:
    key = (forced_agent, suggested_agent)
    return _SWITCH_REASONS.get(
        key,
        f"The {suggested_agent.title()} agent seems better suited for this request.",
    )
