AGENT_METADATA = {
    "auto": {
        "id":           "auto",
        "name":         "Auto (Orchestrator)",
        "description":  "Automatically selects the best agent for your request",
        "capabilities": ["Math calculations", "Mall & food ordering", "Smart routing"],
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
}

_SWITCH_REASONS: dict[tuple, str] = {
    ("calculator", "mall"):       "Your request seems to involve mall or store info — the Mall Assistant handles that better.",
    ("mall",       "calculator"): "Your request involves math — the Calculator agent handles that better.",
}


def get_suggestion_reason(forced_agent: str, suggested_agent: str) -> str:
    key = (forced_agent, suggested_agent)
    return _SWITCH_REASONS.get(
        key,
        f"The {suggested_agent.title()} agent seems better suited for this request.",
    )
