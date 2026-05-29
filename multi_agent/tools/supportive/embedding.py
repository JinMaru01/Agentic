import json
import numpy as np
import faiss
import hashlib
from pathlib import Path
from sentence_transformers import SentenceTransformer
from datetime import datetime, timezone

# =========================
# PATHS
# =========================
_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "stores.json"
_INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "faiss.index"
_META_PATH = Path(__file__).parent.parent.parent / "data" / "index_meta.json"

# =========================
# UTILS
# =========================
def now_utc_iso():
    return datetime.now(timezone.utc).isoformat()


def _load_stores() -> list[dict]:
    with open(_DATA_PATH, "r") as f:
        return json.load(f)


stores: list[dict] = _load_stores()

# =========================
# HASHING
# =========================
def compute_stores_hash(stores: list[dict]) -> str:
    raw = json.dumps(stores, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def save_version(hash_value: str, store_texts: list[str]):
    data = []

    if _META_PATH.exists():
        with open(_META_PATH, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []

    data.append({
        "hash": hash_value,
        "updated_at": now_utc_iso(),
        "store_texts": store_texts
    })

    with open(_META_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_latest_version():
    if not _META_PATH.exists():
        return None

    with open(_META_PATH, "r") as f:
        data = json.load(f)

    if not data:
        return None

    return data[-1]


# =========================
# EMBEDDING MODEL (lazy)
# =========================
_embed_model: SentenceTransformer | None = None
_faiss_index: faiss.IndexFlatIP | None = None
_store_texts: list[str] = []


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


# =========================
# TEXT BUILDER
# =========================
def build_store_text(store):
    menu_text = []

    for item in store.get("menu", []):
        item_text = (
            f"Food: {item.get('name')} "
            f"Description: {item.get('description')} "
            f"Ingredients: {', '.join(item.get('ingredients', []))} "
            f"Price: {item.get('price')} {item.get('currency', 'SGD')}"
        )
        menu_text.append(item_text)

    return (
        f"Store: {store.get('name')} "
        f"Category: {store.get('category')} "
        f"Rating: {store.get('rating', '')} "
        f"Hours: {store.get('storeHours', {}).get('open')} to {store.get('storeHours', {}).get('close')} "
        f"Menu: {' | '.join(menu_text)}"
    )


# =========================
# FAISS INDEX
# =========================
def get_faiss_index() -> faiss.IndexFlatIP:
    global _faiss_index, _store_texts

    if _faiss_index is not None:
        return _faiss_index

    model = get_embed_model()
    current_hash = compute_stores_hash(stores)

    saved_version = load_latest_version()
    saved_hash = saved_version["hash"] if saved_version else None

    needs_rebuild = (
        not _INDEX_PATH.exists()
        or saved_version is None
        or saved_hash != current_hash
    )

    # =========================
    # LOAD EXISTING INDEX
    # =========================
    if not needs_rebuild:
        _faiss_index = faiss.read_index(str(_INDEX_PATH))
        _store_texts = saved_version["store_texts"]
        return _faiss_index

    # =========================
    # REBUILD INDEX
    # =========================
    _store_texts = [build_store_text(s) for s in stores]

    embeddings = model.encode(_store_texts, convert_to_numpy=True)
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    _faiss_index = faiss.IndexFlatIP(dim)
    _faiss_index.add(embeddings.astype(np.float32))

    # =========================
    # SAVE ARTIFACTS (VERSIONED)
    # =========================
    faiss.write_index(_faiss_index, str(_INDEX_PATH))
    save_version(current_hash, _store_texts)

    return _faiss_index


# =========================
# SEARCH
# =========================
def search_stores_by_query(query: str, top_k: int = 3) -> list[dict]:
    """Semantic search over stores using FAISS."""
    model = get_embed_model()
    index = get_faiss_index()

    q_emb = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(q_emb)

    distances, indices = index.search(q_emb.astype(np.float32), top_k)

    results = []
    for i in indices[0]:
        if 0 <= i < len(stores):
            results.append(stores[i])

    return results
