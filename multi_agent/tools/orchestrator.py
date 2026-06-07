from ..agent.calculator import CalculatorAgent
from ..agent.mall import MallAgent
from ..agent.browser import BrowserAgent
from ..agent.search import SearchAgent


# =========================================================
# AGENT REGISTRY
# =========================================================
# Add new agents here as you build them.
# =========================================================

def build_registry(config) -> dict:

    return {
        "calculator": CalculatorAgent(config),
        "mall":       MallAgent(config),
        "browser":    BrowserAgent(config),
        "search":     SearchAgent(config),
    }


# =========================================================
# ROUTER
# =========================================================

def route_query(route_to: str, registry: dict) -> str:
    """Maps route_to value to the next graph node."""
    return route_to if route_to in registry else "fallback"
