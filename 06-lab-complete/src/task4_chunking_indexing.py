"""
Task 4 - Chunking & Indexing vao Vector Store.

Pipeline:
    1. Doc toan bo markdown files tu data/standardized/
    2. Chunk bang RecursiveCharacterTextSplitter
    3. Embed chunks bang Cohere Embed API
    4. Luu local index va index vao Weaviate Cloud
"""

from __future__ import annotations

import json
import os
import time
import hashlib
from pathlib import Path
from typing import Iterable

import numpy as np
import requests
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
INDEX_DIR = PROJECT_DIR / "data" / "index"


# =============================================================================
# CONFIGURATION - chosen for Vietnamese legal/news RAG
# =============================================================================

# RecursiveCharacterTextSplitter is the safest default for mixed markdown:
# legal documents have long articles, while news files have short paragraphs.
# It keeps paragraph/sentence boundaries when possible and degrades gracefully.
CHUNKING_METHOD = "recursive"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# Cohere multilingual embeddings are used because this machine has no GPU and
# the corpus is Vietnamese. embed-multilingual-v3.0 returns 1024-dimensional
# vectors and is suitable for semantic retrieval across Vietnamese text.
EMBEDDING_PROVIDER = "cohere"
EMBEDDING_MODEL = "embed-multilingual-v3.0"
EMBEDDING_DIM = 1024
EMBED_BATCH_SIZE = 48
EMBED_MAX_RETRIES = 6

# Weaviate is the recommended vector store for this assignment. We provide our
# own Cohere vectors, so the Weaviate collection disables built-in vectorizers.
VECTOR_STORE = "weaviate"
COLLECTION_NAME = "DrugLawDocs"


def load_documents() -> list[dict]:
    """
    Doc toan bo markdown files tu data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    documents: list[dict] = []

    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if md_file.name.startswith("."):
            continue

        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        relative_path = md_file.relative_to(STANDARDIZED_DIR).as_posix()
        doc_type = md_file.parent.name if md_file.parent != STANDARDIZED_DIR else "unknown"

        documents.append(
            {
                "content": content,
                "metadata": {
                    "source": md_file.name,
                    "type": doc_type,
                    "path": relative_path,
                },
            }
        )

    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents bang RecursiveCharacterTextSplitter.

    Returns:
        List of {'content': str, 'metadata': dict}
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )

    chunks: list[dict] = []
    for doc_id, doc in enumerate(documents):
        splits = splitter.split_text(doc["content"])
        for chunk_index, chunk_text in enumerate(splits):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            chunks.append(
                {
                    "content": chunk_text,
                    "metadata": {
                        **doc["metadata"],
                        "doc_id": doc_id,
                        "chunk_index": chunk_index,
                    },
                }
            )

    return chunks


def _batched(items: list[str], batch_size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _cohere_embed(texts: list[str], input_type: str = "search_document") -> list[list[float]]:
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing COHERE_API_KEY in .env")

    response = None
    for attempt in range(1, EMBED_MAX_RETRIES + 1):
        response = requests.post(
            "https://api.cohere.ai/v1/embed",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "texts": texts,
                "input_type": input_type,
                "truncate": "END",
            },
            timeout=90,
        )

        if response.status_code != 429:
            response.raise_for_status()
            break

        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            wait_seconds = int(retry_after)
        else:
            wait_seconds = min(90, 2 ** attempt * 3)

        print(
            f"  Cohere rate limit on attempt {attempt}/{EMBED_MAX_RETRIES}; "
            f"waiting {wait_seconds}s"
        )
        time.sleep(wait_seconds)
    else:
        assert response is not None
        response.raise_for_status()

    embeddings = response.json()["embeddings"]
    for embedding in embeddings:
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(
                f"Unexpected embedding dimension {len(embedding)}; expected {EMBEDDING_DIM}"
            )

    return embeddings


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toan bo chunks bang Cohere multilingual embedding model.

    Returns:
        Moi chunk dict duoc them key 'embedding': list[float]
    """
    if not chunks:
        return []

    cached = load_cached_embeddings(chunks)
    if cached is not None:
        print(f"Loaded cached embeddings from {INDEX_DIR}")
        return cached

    texts = [chunk["content"] for chunk in chunks]
    all_embeddings: list[list[float]] = []

    for batch_number, batch in enumerate(_batched(texts, EMBED_BATCH_SIZE), 1):
        print(f"Embedding batch {batch_number}: {len(batch)} chunks")
        all_embeddings.extend(_cohere_embed(batch, input_type="search_document"))

    for chunk, embedding in zip(chunks, all_embeddings):
        chunk["embedding"] = embedding

    return chunks


def chunks_signature(chunks: list[dict]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk["content"].encode("utf-8"))
        digest.update(json.dumps(chunk["metadata"], sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def load_cached_embeddings(chunks: list[dict]) -> list[dict] | None:
    meta_path = INDEX_DIR / "index_meta.json"
    embeddings_path = INDEX_DIR / "embeddings.npy"

    if not meta_path.exists() or not embeddings_path.exists():
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        embeddings = np.load(embeddings_path)
    except Exception:
        return None

    has_matching_signature = meta.get("chunks_signature") == chunks_signature(chunks)
    is_legacy_match = (
        meta.get("num_chunks") == len(chunks)
        and meta.get("embedding_model") == EMBEDDING_MODEL
        and embeddings.shape == (len(chunks), EMBEDDING_DIM)
    )
    if not has_matching_signature and not is_legacy_match:
        return None

    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.astype(float).tolist()
    return chunks


def save_local_index(chunks: list[dict]) -> None:
    """Save chunks and vectors locally for debugging and downstream tasks."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    chunk_records = [
        {"content": chunk["content"], "metadata": chunk["metadata"]}
        for chunk in chunks
    ]
    embeddings = np.array([chunk["embedding"] for chunk in chunks], dtype=np.float32)

    (INDEX_DIR / "chunks.json").write_text(
        json.dumps(chunk_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    np.save(INDEX_DIR / "embeddings.npy", embeddings)
    (INDEX_DIR / "index_meta.json").write_text(
        json.dumps(
            {
                "chunking_method": CHUNKING_METHOD,
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
                "embedding_provider": EMBEDDING_PROVIDER,
                "embedding_model": EMBEDDING_MODEL,
                "embedding_dim": EMBEDDING_DIM,
                "vector_store": VECTOR_STORE,
                "weaviate_collection": COLLECTION_NAME,
                "num_chunks": len(chunks),
                "chunks_signature": chunks_signature(chunks),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _connect_weaviate():
    import weaviate
    from weaviate.classes.init import Auth

    weaviate_url = os.getenv("WEAVIATE_URL")
    weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
    if not weaviate_url or not weaviate_api_key:
        raise RuntimeError("Missing WEAVIATE_URL or WEAVIATE_API_KEY in .env")

    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            return weaviate.connect_to_weaviate_cloud(
                cluster_url=weaviate_url,
                auth_credentials=Auth.api_key(weaviate_api_key),
            )
        except Exception as exc:
            last_error = exc
            wait_seconds = min(60, attempt * 10)
            print(f"Weaviate connection attempt {attempt}/5 failed; waiting {wait_seconds}s")
            time.sleep(wait_seconds)

    assert last_error is not None
    raise last_error


def index_to_vectorstore(chunks: list[dict]) -> None:
    """
    Luu chunks vao local index va Weaviate Cloud.
    """
    if not chunks:
        raise ValueError("No chunks to index")

    save_local_index(chunks)
    print(f"Saved local index to {INDEX_DIR}")

    import weaviate
    from weaviate.classes.config import Configure, DataType, Property

    client = _connect_weaviate()
    try:
        if client.collections.exists(COLLECTION_NAME):
            client.collections.delete(COLLECTION_NAME)

        collection = client.collections.create(
            name=COLLECTION_NAME,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="content", data_type=DataType.TEXT),
                Property(name="source", data_type=DataType.TEXT),
                Property(name="doc_type", data_type=DataType.TEXT),
                Property(name="path", data_type=DataType.TEXT),
                Property(name="doc_id", data_type=DataType.INT),
                Property(name="chunk_index", data_type=DataType.INT),
            ],
        )

        with collection.batch.dynamic() as batch:
            for chunk in chunks:
                metadata = chunk["metadata"]
                batch.add_object(
                    properties={
                        "content": chunk["content"],
                        "source": metadata["source"],
                        "doc_type": metadata["type"],
                        "path": metadata["path"],
                        "doc_id": int(metadata["doc_id"]),
                        "chunk_index": int(metadata["chunk_index"]),
                    },
                    vector=chunk["embedding"],
                )

        failed = collection.batch.failed_objects
        if failed:
            raise RuntimeError(f"Weaviate batch failed for {len(failed)} objects")

        print(f"Indexed {len(chunks)} chunks to Weaviate collection {COLLECTION_NAME}")
    except weaviate.exceptions.WeaviateBaseError:
        raise
    finally:
        client.close()


def run_pipeline() -> list[dict]:
    """Chay toan bo pipeline: load -> chunk -> embed -> index."""
    print("=" * 60)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_PROVIDER}/{EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE} ({COLLECTION_NAME})")
    print("=" * 60)

    docs = load_documents()
    print(f"\nLoaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("Indexed to vector store")
    return chunks


if __name__ == "__main__":
    run_pipeline()
