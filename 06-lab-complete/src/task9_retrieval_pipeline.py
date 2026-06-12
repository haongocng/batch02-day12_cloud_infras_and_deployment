"""
Task 9 - Complete Retrieval Pipeline.

Pipeline:
    Query
      -> Semantic Search (Task 5)
      -> Lexical Search  (Task 6)
      -> Merge with RRF
      -> Rerank with Jina (Task 7)
      -> Fallback to PageIndex (Task 8) if quality is too low
"""

from __future__ import annotations

try:
    from .task5_semantic_search import semantic_search
    from .task6_lexical_search import lexical_search
    from .task7_reranking import rerank, rerank_rrf
    from .task8_pageindex_vectorless import pageindex_search
except ImportError:  # Allows running this file directly
    from task5_semantic_search import semantic_search  # type: ignore
    from task6_lexical_search import lexical_search  # type: ignore
    from task7_reranking import rerank, rerank_rrf  # type: ignore
    from task8_pageindex_vectorless import pageindex_search  # type: ignore


SCORE_THRESHOLD = 0.3
DEFAULT_TOP_K = 5
RERANK_METHOD = "cross_encoder"
RETRIEVER_MULTIPLIER = 3


def _with_retriever_source(results: list[dict], retriever: str) -> list[dict]:
    tagged: list[dict] = []
    for result in results:
        item = dict(result)
        metadata = dict(item.get("metadata", {}))
        metadata["retriever"] = retriever
        item["metadata"] = metadata
        tagged.append(item)
    return tagged


def _mark_hybrid(results: list[dict]) -> list[dict]:
    marked: list[dict] = []
    for result in results:
        item = dict(result)
        item["source"] = "hybrid"
        item.setdefault("metadata", {})
        marked.append(item)
    return marked


def _fallback(query: str, top_k: int) -> list[dict]:
    fallback_results = pageindex_search(query, top_k=top_k)
    for result in fallback_results:
        result["source"] = "pageindex"
    return fallback_results[:top_k]


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """
    Complete retrieval pipeline with fallback logic.

    Steps:
        1. Run semantic_search + lexical_search
        2. Merge results with RRF
        3. Rerank merged candidates
        4. If top score is below threshold, fallback to PageIndex
        5. Return top_k results

    Returns:
        List of {'content': str, 'score': float, 'metadata': dict, 'source': str}
    """
    if top_k <= 0 or not query.strip():
        return []

    candidate_k = max(top_k * RETRIEVER_MULTIPLIER, top_k)

    try:
        dense_results = semantic_search(query, top_k=candidate_k)
    except Exception as exc:
        print(f"Semantic search failed: {exc}")
        dense_results = []

    try:
        sparse_results = lexical_search(query, top_k=candidate_k)
    except Exception as exc:
        print(f"Lexical search failed: {exc}")
        sparse_results = []

    dense_results = _with_retriever_source(dense_results, "semantic")
    sparse_results = _with_retriever_source(sparse_results, "lexical")

    if not dense_results and not sparse_results:
        return _fallback(query, top_k)

    merged = rerank_rrf(
        [dense_results, sparse_results],
        top_k=candidate_k,
    )
    merged = _mark_hybrid(merged)

    if use_reranking and merged:
        try:
            final_results = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
            final_results = _mark_hybrid(final_results)
        except Exception as exc:
            print(f"Reranking failed: {exc}")
            final_results = merged[:top_k]
    else:
        final_results = merged[:top_k]

    if not final_results:
        return _fallback(query, top_k)

    best_score = float(final_results[0].get("score", 0.0))
    if best_score < score_threshold:
        fallback_results = _fallback(query, top_k)
        if fallback_results:
            return fallback_results

    return final_results[:top_k]


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma túy",
        "Nghệ sĩ nào bị bắt vì sử dụng ma túy",
        "Luật phòng chống ma túy 2021 quy định gì về cai nghiện",
    ]

    for question in test_queries:
        print(f"\nQuery: {question}")
        print("-" * 80)
        for i, result in enumerate(retrieve(question, top_k=3), 1):
            print(
                f"{i}. [{result['score']:.3f}] [{result['source']}] "
                f"{result['metadata'].get('source')}: {result['content'][:100]}..."
            )
