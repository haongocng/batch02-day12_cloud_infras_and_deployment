"""
Task 5 - Semantic Search Module.

Dense retrieval uses the same embedding model as Task 4:
    Cohere embed-multilingual-v3.0, 1024 dimensions.

Primary path:
    query -> Cohere query embedding -> Weaviate near_vector search

Fallback path:
    query -> Cohere query embedding -> local cosine search over data/index
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

try:
    from .task4_chunking_indexing import (
        COLLECTION_NAME,
        EMBEDDING_DIM,
        EMBEDDING_MODEL,
        INDEX_DIR,
        _cohere_embed,
        _connect_weaviate,
    )
except ImportError:  # Allows running this file directly: python src/task5_semantic_search.py
    from task4_chunking_indexing import (  # type: ignore
        COLLECTION_NAME,
        EMBEDDING_DIM,
        EMBEDDING_MODEL,
        INDEX_DIR,
        _cohere_embed,
        _connect_weaviate,
    )

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent


def embed_query(query: str) -> list[float]:
    """Embed query with the same Cohere model used for document chunks."""
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")

    embedding = _cohere_embed([query], input_type="search_query")[0]
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(
            f"Unexpected query embedding dimension {len(embedding)}; "
            f"expected {EMBEDDING_DIM} from {EMBEDDING_MODEL}"
        )
    return embedding


def _metadata_from_weaviate_properties(properties: dict) -> dict:
    return {
        "source": properties.get("source"),
        "type": properties.get("doc_type"),
        "path": properties.get("path"),
        "doc_id": properties.get("doc_id"),
        "chunk_index": properties.get("chunk_index"),
    }


def _search_weaviate(query_embedding: list[float], top_k: int) -> list[dict]:
    from weaviate.classes.query import MetadataQuery

    client = _connect_weaviate()
    try:
        collection = client.collections.get(COLLECTION_NAME)
        response = collection.query.near_vector(
            near_vector=query_embedding,
            limit=top_k,
            return_metadata=MetadataQuery(distance=True),
        )

        results: list[dict] = []
        for obj in response.objects:
            distance = getattr(obj.metadata, "distance", None)
            score = 1.0 - float(distance) if distance is not None else 0.0
            properties = obj.properties or {}
            results.append(
                {
                    "content": properties.get("content", ""),
                    "score": score,
                    "metadata": _metadata_from_weaviate_properties(properties),
                }
            )

        return sorted(results, key=lambda item: item["score"], reverse=True)
    finally:
        client.close()


def _search_local(query_embedding: list[float], top_k: int) -> list[dict]:
    chunks_path = INDEX_DIR / "chunks.json"
    embeddings_path = INDEX_DIR / "embeddings.npy"
    if not chunks_path.exists() or not embeddings_path.exists():
        return []

    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    embeddings = np.load(embeddings_path).astype(np.float32)

    query_vector = np.array(query_embedding, dtype=np.float32)
    query_norm = np.linalg.norm(query_vector)
    embedding_norms = np.linalg.norm(embeddings, axis=1)

    denominator = embedding_norms * query_norm
    denominator[denominator == 0] = 1e-12
    scores = embeddings @ query_vector / denominator

    top_indices = np.argsort(scores)[::-1][:top_k]
    results: list[dict] = []
    for idx in top_indices:
        chunk = chunks[int(idx)]
        results.append(
            {
                "content": chunk["content"],
                "score": float(scores[int(idx)]),
                "metadata": chunk.get("metadata", {}),
            }
        )

    return sorted(results, key=lambda item: item["score"], reverse=True)


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tim kiem ngu nghia su dung dense vector similarity.

    Args:
        query: Cau truy van
        top_k: So luong ket qua toi da

    Returns:
        List of {'content': str, 'score': float, 'metadata': dict}
        sorted by score descending.
    """
    if top_k <= 0:
        return []

    query_embedding = embed_query(query)

    try:
        return _search_weaviate(query_embedding, top_k=top_k)
    except Exception as exc:
        print(f"Weaviate semantic search failed, using local fallback: {exc}")
        return _search_local(query_embedding, top_k=top_k)


if __name__ == "__main__":
    results = semantic_search("hình phạt cho tội tàng trữ ma túy", top_k=5)
    for result in results:
        source = result["metadata"].get("source")
        print(f"[{result['score']:.3f}] {source}: {result['content'][:120]}...")
