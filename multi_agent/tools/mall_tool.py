import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from .supportive.embedding import stores, search_stores_by_query

_ORDERS_DIR = Path(__file__).parent.parent / "data"
_ORDERS_JSON = _ORDERS_DIR / "orders.json"
_ORDERS_CSV = _ORDERS_DIR / "orders.csv"

_CSV_FIELDS = ["order_id", "store", "item", "quantity", "price", "currency", "status", "placed_at"]


def _save_order(order: dict) -> None:
    """Append a confirmed order to orders.json and orders.csv."""
    _ORDERS_DIR.mkdir(parents=True, exist_ok=True)

    record = {**order, "placed_at": datetime.now(timezone.utc).isoformat()}

    # --- JSON ---
    existing: list = []
    if _ORDERS_JSON.exists():
        try:
            existing = json.loads(_ORDERS_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append(record)
    _ORDERS_JSON.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- CSV ---
    write_header = not _ORDERS_CSV.exists()
    with _ORDERS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(record)


# =========================
# STORE INDEX
# Built once at module load for O(1) name lookups instead of O(n) scans.
# =========================

_store_index: dict[str, dict] = {s["name"].lower(): s for s in stores}


# =========================
# LANGCHAIN TOOL FUNCTIONS
# =========================

@tool
def search_store(query: str) -> list[dict]:
    """Find stores by semantic similarity to query.

    Returns a list of store dicts as provided by search_stores_by_query.
    Each dict is expected to contain at least: name (str), and either
    menu (list[str]) or services (list[str]).
    """
    results = search_stores_by_query(query)
    if not isinstance(results, list):
        return []
    return results


@tool
def get_menu(store_name: str) -> list[str]:
    """Return available menu items or services for a store.

    Uses an O(1) index lookup. Unavailable items (isAvailable=false) are
    excluded at the tool level so the agent never sees or suggests them.
    Returns an empty list if the store is not found.
    """
    store = _store_index.get(store_name.lower())
    if store is None:
        return []
    items = store.get("menu", store.get("services", []))
    return [
        item for item in items
        if not isinstance(item, dict) or item.get("isAvailable", True)
    ]


@tool
def place_order(store_name: str, item: str, quantity: int = 1) -> dict:
    """Place an order after verifying store and item exist and are available.

    STRICT PRECONDITIONS — only call this tool when ALL of the following are true:
      1. The user has explicitly confirmed with "yes", "ok", "confirm", "go ahead",
         "proceed", "place it", or equivalent.
      2. store_name and item were obtained from search_store / get_menu in this session.
      3. quantity is a positive integer (1–20).
    Never call this tool autonomously or before explicit confirmation.

    Returns a confirmed order dict on success, or an error dict on failure.
    """
    if not isinstance(quantity, int) or quantity < 1 or quantity > 20:
        return {
            "status":  "error",
            "message": f"Quantity must be a whole number between 1 and 20, got '{quantity}'.",
        }

    menu = get_menu.run(store_name)

    if not menu:
        return {
            "status":  "error",
            "message": f"Store '{store_name}' was not found in the mall database.",
        }

    matched_item = None
    for m in menu:
        name = m["name"] if isinstance(m, dict) else m
        if (name.lower() if isinstance(name, str) else "") == item.lower():
            matched_item = m
            break

    if not matched_item:
        menu_names = [m["name"] if isinstance(m, dict) else m for m in menu]
        return {
            "status":  "error",
            "message": (
                f"'{item}' is not available at {store_name}. "
                f"Currently available: {menu_names}"
            ),
        }

    price    = matched_item.get("price", 0.0) if isinstance(matched_item, dict) else 0.0
    currency = matched_item.get("currency", "USD") if isinstance(matched_item, dict) else "USD"

    order = {
        "status":   "confirmed",
        "store":    store_name,
        "item":     item,
        "price":    price,
        "currency": currency,
        "quantity": quantity,
        "order_id": "ORD-" + str(uuid.uuid4())[:8].upper(),
    }
    _save_order(order)
    return order

tools: list = [search_store, get_menu, place_order]