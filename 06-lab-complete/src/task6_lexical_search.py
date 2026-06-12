"""
Task 6 - Lexical Search Module (BM25).

This module performs keyword-based retrieval over the same chunks indexed in
Task 4. BM25 complements semantic search because exact legal terms such as
"Điều 249", decree numbers, names, and quoted phrases often matter.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

PROJECT_DIR = Path(__file__).parent.parent
INDEX_DIR = PROJECT_DIR / "data" / "index"
CHUNKS_PATH = INDEX_DIR / "chunks.json"


def strip_vietnamese_accents(text: str) -> str:
    """Remove accents so queries with or without Vietnamese tone marks can match."""
    normalized = unicodedata.normalize("NFD", text)
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return without_marks.replace("đ", "d").replace("Đ", "D")


def tokenize(text: str) -> list[str]:
    """
    Simple Vietnamese-friendly tokenizer for BM25.

    It keeps letters and numbers, lowercases text, and adds both original and
    accent-stripped tokens. This improves matching for queries like "ma tuy"
    against documents containing "ma túy".
    """
    lowered = text.lower()
    no_accents = strip_vietnamese_accents(lowered)

    original_tokens = re.findall(r"[\w]+", lowered, flags=re.UNICODE)
    normalized_tokens = re.findall(r"[\w]+", no_accents, flags=re.UNICODE)

    return original_tokens + normalized_tokens


def load_corpus() -> list[dict]:
    """Load chunk corpus produced by Task 4."""
    if not CHUNKS_PATH.exists():
        return []

    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    return [
        {
            "content": item.get("content", ""),
            "metadata": item.get("metadata", {}),
        }
        for item in chunks
        if item.get("content", "").strip()
    ]


def build_bm25_index(corpus: list[dict]) -> BM25Okapi:
    """
    Xay dung BM25 index tu corpus.

    Args:
        corpus: List of {'content': str, 'metadata': dict}
    """
    tokenized_corpus = [tokenize(doc["content"]) for doc in corpus]
    return BM25Okapi(tokenized_corpus)


@lru_cache(maxsize=1)
def get_bm25_resources() -> tuple[list[dict], BM25Okapi]:
    """Build and cache BM25 resources for repeated searches."""
    corpus = load_corpus()
    if not corpus:
        return [], BM25Okapi([["empty"]])

    return corpus, build_bm25_index(corpus)


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tim kiem tu khoa su dung BM25.

    Args:
        query: Cau truy van
        top_k: So luong ket qua toi da

    Returns:
        List of {'content': str, 'score': float, 'metadata': dict}
        sorted by score descending.
    """
    if top_k <= 0 or not query.strip():
        return []

    corpus, bm25 = get_bm25_resources()
    if not corpus:
        return []

    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    top_indices = np.argsort(scores)[::-1][:top_k]
    results: list[dict] = []
    for idx in top_indices:
        score = float(scores[int(idx)])
        if score <= 0:
            continue

        results.append(
            {
                "content": corpus[int(idx)]["content"],
                "score": score,
                "metadata": corpus[int(idx)].get("metadata", {}),
            }
        )

    return sorted(results, key=lambda item: item["score"], reverse=True)


if __name__ == "__main__":
    results = lexical_search("Điều 249 tàng trữ trái phép chất ma túy", top_k=5)
    for result in results:
        source = result["metadata"].get("source")
        print(f"[{result['score']:.3f}] {source}: {result['content'][:120]}...")
