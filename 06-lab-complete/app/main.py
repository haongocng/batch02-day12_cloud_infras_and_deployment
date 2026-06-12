"""Production API wrapper for the Day 08 DrugLaw RAG project."""

from __future__ import annotations

import json
import logging
import signal
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

from app.config import settings


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = PROJECT_ROOT / "data" / "index"
CHUNKS_PATH = INDEX_DIR / "chunks.json"

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if api_key != settings.agent_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str) -> dict[str, int]:
    now = time.time()
    window = _rate_windows[key]

    while window and window[0] < now - 60:
        window.popleft()

    if len(window) >= settings.rate_limit_per_minute:
        retry_after = int(window[0] + 60 - now) + 1
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": settings.rate_limit_per_minute,
                "window_seconds": 60,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    window.append(now)
    return {
        "limit": settings.rate_limit_per_minute,
        "remaining": settings.rate_limit_per_minute - len(window),
    }


# ---------------------------------------------------------------------------
# Cost guard
# ---------------------------------------------------------------------------
_daily_cost = 0.0
_cost_reset_day = time.strftime("%Y-%m-%d")


def check_and_record_cost(input_tokens: int, output_tokens: int) -> dict[str, float]:
    global _daily_cost, _cost_reset_day

    today = time.strftime("%Y-%m-%d")
    if today != _cost_reset_day:
        _daily_cost = 0.0
        _cost_reset_day = today

    estimated_cost = (input_tokens / 1000 * 0.00015) + (output_tokens / 1000 * 0.0006)
    if _daily_cost + estimated_cost > settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "budget_usd": settings.daily_budget_usd,
                "current_cost_usd": round(_daily_cost, 6),
                "estimated_request_cost_usd": round(estimated_cost, 6),
            },
        )

    _daily_cost += estimated_cost
    return {
        "request_cost_usd": round(estimated_cost, 6),
        "daily_cost_usd": round(_daily_cost, 6),
        "daily_budget_usd": settings.daily_budget_usd,
        "budget_remaining_usd": round(max(0, settings.daily_budget_usd - _daily_cost), 6),
    }


# ---------------------------------------------------------------------------
# RAG adapter
# ---------------------------------------------------------------------------
def _rag_ready() -> bool:
    return CHUNKS_PATH.exists()


def _load_rag_generator():
    from src.task10_generation import generate_with_citation

    return generate_with_citation


def _trim_source(source: dict[str, Any], max_chars: int = 900) -> dict[str, Any]:
    metadata = source.get("metadata", {}) or {}
    return {
        "content": str(source.get("content", ""))[:max_chars],
        "score": float(source.get("score", 0.0)),
        "metadata": {
            "source": metadata.get("source"),
            "type": metadata.get("type") or metadata.get("doc_type"),
            "path": metadata.get("path"),
            "retriever": metadata.get("retriever"),
            "chunk_index": metadata.get("chunk_index"),
        },
        "retrieval_source": source.get("source"),
    }


# ---------------------------------------------------------------------------
# FastAPI lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({"event": "startup", "app": settings.app_name}))
    _is_ready = True
    logger.info(json.dumps({"event": "ready", "rag_index": str(CHUNKS_PATH)}))
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    request_id = f"req-{int(time.time() * 1000)}"
    start = time.time()
    _request_count += 1

    try:
        response: Response = await call_next(request)
        return response
    except Exception:
        _error_count += 1
        logger.exception(json.dumps({"event": "request_error", "request_id": request_id}))
        raise
    finally:
        duration_ms = round((time.time() - start) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                }
            )
        )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1200)
    top_k: int = Field(default=5, ge=1, le=8)
    use_reranking: bool = True


class AskResponse(BaseModel):
    question: str
    answer: str
    confidence: str
    retrieval_source: str
    sources: list[dict[str, Any]]
    usage: dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "project": "Day08 DrugLaw RAG",
        "endpoints": {
            "ask": "POST /ask",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(body: AskRequest, api_key: str = Depends(verify_api_key)):
    rate_info = check_rate_limit(api_key[:12])

    try:
        generator = _load_rag_generator()
        result = generator(
            body.question,
            top_k=body.top_k,
            use_reranking=body.use_reranking,
        )
    except Exception as exc:
        _error = {
            "event": "rag_generation_failed",
            "error": str(exc),
            "question_length": len(body.question),
        }
        logger.error(json.dumps(_error))
        raise HTTPException(status_code=503, detail="RAG generation failed") from exc

    answer = result.get("answer", "")
    sources = [_trim_source(source) for source in result.get("sources", [])]

    input_tokens = max(1, len(body.question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2)
    cost_info = check_and_record_cost(input_tokens, output_tokens)

    return AskResponse(
        question=body.question,
        answer=answer,
        confidence=result.get("confidence", "unknown"),
        retrieval_source=result.get("retrieval_source", "unknown"),
        sources=sources,
        usage={
            "rate_limit": rate_info,
            "cost": cost_info,
            "model": settings.llm_model,
            "input_tokens_estimate": input_tokens,
            "output_tokens_estimate": output_tokens,
        },
    )


@app.get("/health", tags=["Operations"])
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "rag_index": "ok" if _rag_ready() else "missing",
            "llm": "openrouter/openai"
            if (settings.openrouter_api_key or settings.openai_api_key)
            else "fallback",
            "providers": {
                "jina_reranking": bool(settings.jina_api_key),
                "cohere_embeddings": bool(settings.cohere_api_key),
                "weaviate": bool(settings.weaviate_url and settings.weaviate_api_key),
                "pageindex": bool(settings.pageindex_api_key),
            },
        },
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Not ready")
    if not _rag_ready():
        raise HTTPException(status_code=503, detail="RAG local index not found")
    return {"ready": True, "rag_index": str(CHUNKS_PATH)}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)):
    return {
        "requests": _request_count,
        "errors": _error_count,
        "daily_cost_usd": round(_daily_cost, 6),
        "daily_budget_usd": settings.daily_budget_usd,
        "budget_used_pct": round(_daily_cost / settings.daily_budget_usd * 100, 2),
        "rate_limit_per_minute": settings.rate_limit_per_minute,
    }


def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal_received", "signal": signum}))


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
