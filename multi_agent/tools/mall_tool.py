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
    """Return menu items or services for a store.

    Uses an O(1) index lookup instead of a linear scan.
    Returns an empty list if the store is not found.
    """
    store = _store_index.get(store_name.lower())
    if store is None:
        return []
    return store.get("menu", store.get("services", []))


@tool
def place_order(store_name: str, item: str, quantity: int = 1) -> dict:
    """Place an order after verifying store and item exist.

    Returns a confirmed order dict on success, or an error dict on failure.
    Note: this tool is only called after explicit user confirmation —
    never dispatched from the main agent loop autonomously.
    """
    menu = get_menu.run(store_name)

    if not menu:
        return {"status": "error", "message": f"Store '{store_name}' not found."}

    # find the full matched item dict to extract price + currency
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
            "message": f"Item '{item}' not found in {store_name}. Available: {menu_names}",
        }

    order = {
        "status":   "confirmed",
        "store":    store_name,
        "item":     item,
        "price":    matched_item.get("price", 0.0),
        "currency": matched_item.get("currency", "USD"),
        "quantity": quantity,
        "order_id": "ORD-" + str(uuid.uuid4())[:8].upper(),
    }
    _save_order(order)
    return order

tools: list = [search_store, get_menu, place_order]