"""
Task 8 - PageIndex Vectorless RAG.

PageIndex is used as a fallback retriever when hybrid retrieval is not good
enough. The installed SDK expects file paths for document upload and doc_id for
queries, so this module keeps a small local manifest of uploaded documents.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from pageindex import PageIndexClient, PageIndexAPIError
except ImportError:  # pragma: no cover - handled gracefully at runtime
    PageIndexClient = None  # type: ignore
    PageIndexAPIError = Exception  # type: ignore

try:
    from .task6_lexical_search import lexical_search
except ImportError:  # Allows running directly: python src/task8_pageindex_vectorless.py
    from task6_lexical_search import lexical_search  # type: ignore

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
INDEX_DIR = PROJECT_DIR / "data" / "index"
PAGEINDEX_MANIFEST = INDEX_DIR / "pageindex_documents.json"
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")


def _client() -> Any:
    if not PAGEINDEX_API_KEY:
        raise RuntimeError("Missing PAGEINDEX_API_KEY in .env")
    if PageIndexClient is None:
        raise RuntimeError("PageIndex SDK is not installed")
    return PageIndexClient(api_key=PAGEINDEX_API_KEY)


def load_markdown_files() -> list[dict]:
    """Load markdown file paths from data/standardized."""
    documents: list[dict] = []
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        if not md_file.read_text(encoding="utf-8").strip():
            continue
        documents.append(
            {
                "file_path": str(md_file.resolve()),
                "filename": md_file.name,
                "type": md_file.parent.name,
                "path": md_file.relative_to(STANDARDIZED_DIR).as_posix(),
            }
        )
    return documents


def _extract_doc_id(response: Any) -> str | None:
    if isinstance(response, dict):
        for key in ("doc_id", "document_id", "id"):
            if response.get(key):
                return str(response[key])
        data = response.get("data")
        if isinstance(data, dict):
            return _extract_doc_id(data)
    return None


def _save_manifest(records: list[dict]) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    PAGEINDEX_MANIFEST.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_manifest() -> list[dict]:
    if not PAGEINDEX_MANIFEST.exists():
        return []
    try:
        return json.loads(PAGEINDEX_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return []


def upload_documents() -> dict[str, int]:
    """
    Upload all markdown documents to PageIndex and store doc_ids locally.

    Returns:
        {'uploaded': int, 'failed': int}
    """
    client = _client()
    documents = load_markdown_files()
    records: list[dict] = []
    stats = {"uploaded": 0, "failed": 0}

    for doc in documents:
        for attempt in range(1, 4):
            try:
                response = client.submit_document(file_path=doc["file_path"])
                doc_id = _extract_doc_id(response)
                if not doc_id:
                    raise RuntimeError(f"PageIndex response has no doc_id: {response}")
                records.append({**doc, "doc_id": doc_id})
                stats["uploaded"] += 1
                break
            except Exception:
                if attempt == 3:
                    stats["failed"] += 1
                    break
                time.sleep(2**attempt)

    if records:
        _save_manifest(records)
    return stats


def _extract_query_text(response: Any) -> str:
    if isinstance(response, dict):
        for key in ("answer", "response", "content", "text", "result", "message"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        data = response.get("data")
        if data:
            return _extract_query_text(data)
    if isinstance(response, str):
        return response.strip()
    return ""


def _pageindex_api_search(query: str, top_k: int) -> list[dict]:
    manifest = _load_manifest()
    if not manifest:
        return []

    client = _client()
    results: list[dict] = []

    for rank, record in enumerate(manifest[: max(top_k * 2, top_k)], 1):
        try:
            response = client.submit_query(doc_id=record["doc_id"], query=query)
            content = _extract_query_text(response)
            if not content:
                continue
            results.append(
                {
                    "content": content,
                    "score": 1.0 / rank,
                    "metadata": {
                        "source": record["filename"],
                        "type": record["type"],
                        "path": record["path"],
                        "doc_id": record["doc_id"],
                    },
                    "source": "pageindex",
                }
            )
        except (PageIndexAPIError, Exception):
            continue

    return results[:top_k]


def _local_vectorless_fallback(query: str, top_k: int) -> list[dict]:
    """
    Local keyword fallback used when PageIndex has not been uploaded yet.

    It keeps Task 9 robust while preserving the required PageIndex fallback
    output shape.
    """
    results = lexical_search(query, top_k=top_k)
    for result in results:
        result["source"] = "pageindex"
        result.setdefault("metadata", {})["fallback"] = "local_bm25"
    return results


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval using PageIndex.

    Returns:
        List of {'content': str, 'score': float, 'metadata': dict, 'source': 'pageindex'}
    """
    if top_k <= 0 or not query.strip():
        return []

    try:
        results = _pageindex_api_search(query.strip(), top_k=top_k)
        if results:
            return results
    except Exception as exc:
        print(f"PageIndex API search unavailable, using local fallback: {exc}")

    return _local_vectorless_fallback(query, top_k=top_k)


if __name__ == "__main__":
    for item in pageindex_search("hình phạt tàng trữ ma túy", top_k=3):
        print(f"[{item['score']:.3f}] {item['metadata'].get('source')}: {item['content'][:100]}...")
