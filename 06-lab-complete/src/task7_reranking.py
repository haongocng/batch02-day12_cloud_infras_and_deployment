"""
Task 7 - Reranking Module.

Primary method:
    Jina Reranker API with jina-reranker-v2-base-multilingual.

This is a good fit for the project because the corpus is Vietnamese and the
machine has no GPU. The API acts like a cross-encoder: it scores each
query-document pair directly, then returns the most relevant documents.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable

import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
JINA_RERANK_MODEL = "jina-reranker-v2-base-multilingual"
JINA_MAX_RETRIES = 4


def _candidate_key(candidate: dict) -> str:
    metadata = candidate.get("metadata", {})
    source = metadata.get("source", "")
    chunk_index = metadata.get("chunk_index", "")
    content = candidate.get("content", "")
    return f"{source}:{chunk_index}:{content[:120]}"


def _fallback_by_existing_score(candidates: list[dict], top_k: int) -> list[dict]:
    """Use original retrieval scores when the external reranker is unavailable."""
    sorted_candidates = sorted(
        candidates,
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )
    return [dict(item) for item in sorted_candidates[:top_k]]


def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
    Rerank candidates su dung Jina multilingual cross-encoder API.

    Args:
        query: Cau truy van
        candidates: List of {'content': str, 'score': float, 'metadata': dict}
        top_k: So luong ket qua sau rerank

    Returns:
        List of top_k candidates, re-scored and sorted by relevance.
    """
    if top_k <= 0 or not candidates:
        return []

    api_key = os.getenv("JINA_API_KEY")
    if not api_key:
        print("Missing JINA_API_KEY; using original retrieval scores")
        return _fallback_by_existing_score(candidates, top_k)

    documents = [candidate.get("content", "") for candidate in candidates]
    payload = {
        "model": JINA_RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": min(top_k, len(candidates)),
    }

    response = None
    for attempt in range(1, JINA_MAX_RETRIES + 1):
        try:
            response = requests.post(
                JINA_RERANK_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=90,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                print(f"Jina rate limit on attempt {attempt}; waiting {wait_seconds}s")
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            break
        except requests.RequestException as exc:
            if attempt == JINA_MAX_RETRIES:
                print(f"Jina rerank failed after retries: {exc}")
                return _fallback_by_existing_score(candidates, top_k)
            wait_seconds = 2 ** attempt
            print(f"Jina rerank attempt {attempt} failed; waiting {wait_seconds}s")
            time.sleep(wait_seconds)
    else:
        return _fallback_by_existing_score(candidates, top_k)

    assert response is not None
    data = response.json()
    reranked_items = data.get("results", [])

    results: list[dict] = []
    for item in reranked_items:
        index = int(item["index"])
        relevance_score = float(item.get("relevance_score", item.get("score", 0.0)))
        original = dict(candidates[index])
        original["score"] = relevance_score
        original["rerank_score"] = relevance_score
        original["original_score"] = float(candidates[index].get("score", 0.0))
        original["rerank_model"] = JINA_RERANK_MODEL
        results.append(original)

    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denom == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / denom)


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """
    Maximal Marginal Relevance: select candidates that are relevant and diverse.
    Requires each candidate to have an 'embedding' field.
    """
    if top_k <= 0 or not candidates:
        return []

    query_vec = np.array(query_embedding, dtype=np.float32)
    embeddings = [
        np.array(candidate["embedding"], dtype=np.float32)
        for candidate in candidates
        if "embedding" in candidate
    ]
    if len(embeddings) != len(candidates):
        return _fallback_by_existing_score(candidates, top_k)

    selected: list[int] = []
    remaining = list(range(len(candidates)))

    for _ in range(min(top_k, len(candidates))):
        best_idx = remaining[0]
        best_score = float("-inf")

        for idx in remaining:
            relevance = _cosine_similarity(query_vec, embeddings[idx])
            diversity_penalty = 0.0
            if selected:
                diversity_penalty = max(
                    _cosine_similarity(embeddings[idx], embeddings[selected_idx])
                    for selected_idx in selected
                )
            mmr_score = lambda_param * relevance - (1 - lambda_param) * diversity_penalty

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        selected.append(best_idx)
        remaining.remove(best_idx)

    results = []
    for idx in selected:
        item = dict(candidates[idx])
        item["score"] = float(item.get("score", 0.0))
        item["mmr_selected"] = True
        results.append(item)
    return results


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60
) -> list[dict]:
    """
    Reciprocal Rank Fusion: merge ranked result lists from multiple retrievers.

    RRF(d) = sum(1 / (k + rank_r(d)))
    """
    if top_k <= 0:
        return []

    rrf_scores: dict[str, float] = {}
    content_map: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = _candidate_key(item)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            content_map[key] = item

    sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
    results: list[dict] = []
    for key in sorted_keys[:top_k]:
        item = dict(content_map[key])
        item["score"] = float(rrf_scores[key])
        item["rrf_score"] = float(rrf_scores[key])
        results.append(item)

    return results


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",
) -> list[dict]:
    """
    Re-score and re-order candidates based on relevance to query.
    """
    if top_k <= 0 or not candidates:
        return []

    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    if method == "rrf":
        return rerank_rrf([candidates], top_k=top_k)
    if method == "mmr":
        raise ValueError("MMR requires query_embedding; call rerank_mmr directly.")

    raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    dummy_candidates = [
        {"content": "Điều 249: Tội tàng trữ trái phép chất ma túy", "score": 0.8, "metadata": {}},
        {"content": "Nghệ sĩ X bị bắt vì sử dụng ma túy", "score": 0.7, "metadata": {}},
        {"content": "Hình phạt tù từ 2-7 năm cho tội tàng trữ", "score": 0.6, "metadata": {}},
    ]
    for result in rerank("hình phạt tàng trữ ma túy", dummy_candidates, top_k=2):
        print(f"[{result['score']:.3f}] {result['content']}")
