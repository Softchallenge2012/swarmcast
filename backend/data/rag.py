"""RAG layer — Voyage-3 embeddings over static Kaggle + StatsBomb corpus.
No vector DB: numpy cosine similarity at query time (~500 docs, fast enough).

Offline: call embed_corpus() once to build embeddings.npy + metadata.json.
Runtime: call query() to retrieve top-k context chunks.
"""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import voyageai
from ..config import settings

_DATA_DIR  = Path(__file__).parent / "static"
_EMB_PATH  = _DATA_DIR / "embeddings.npy"
_META_PATH = _DATA_DIR / "metadata.json"

_vc = voyageai.Client(api_key=settings.voyage_api_key)

# Module-level cache — loaded once per process
_embeddings: np.ndarray | None = None
_metadata: list[dict] | None = None


def _load() -> tuple[np.ndarray, list[dict]]:
    global _embeddings, _metadata
    if _embeddings is None:
        _embeddings = np.load(_EMB_PATH)
        _metadata   = json.loads(_META_PATH.read_text())
    return _embeddings, _metadata


def embed_corpus(docs: list[dict]) -> None:
    """Embed the static corpus offline and persist to disk.
    Each doc: {"text": str, "source": str, "tags": list[str]}
    """
    texts = [d["text"] for d in docs]
    result = _vc.embed(texts, model=settings.embedding_model, input_type="document")
    emb = np.array(result.embeddings, dtype=np.float32)
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(_EMB_PATH, emb)
    _META_PATH.write_text(json.dumps(docs, indent=2))


def query(match_query: str, k: int = 10) -> list[str]:
    """Return top-k text chunks most relevant to the match query."""
    emb, meta = _load()
    result = _vc.embed([match_query], model=settings.embedding_model, input_type="query")
    q_vec = np.array(result.embeddings[0], dtype=np.float32)

    # Cosine similarity
    norms = np.linalg.norm(emb, axis=1) * np.linalg.norm(q_vec)
    norms = np.where(norms == 0, 1e-9, norms)
    scores = (emb @ q_vec) / norms
    top_k = np.argsort(scores)[::-1][:k]
    return [meta[i]["text"] for i in top_k]
