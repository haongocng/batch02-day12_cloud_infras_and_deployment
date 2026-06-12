"""
RAG Evaluation Pipeline for the group project.

The script evaluates two retrieval configs on the golden dataset:
    A. hybrid search + Jina reranking
    B. hybrid search without reranking

It reports four required metrics:
    - Faithfulness
    - Answer Relevance
    - Context Recall
    - Context Precision

The default evaluator is a lightweight deterministic evaluator based on token
overlap. It is fast, reproducible, and does not spend extra LLM-judge quota.
The metric names mirror DeepEval/RAGAS-style RAG metrics so the report remains
aligned with the assignment requirements.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path
from typing import Callable

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.task9_retrieval_pipeline import retrieve  # noqa: E402

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"

STOPWORDS = {
    "và", "của", "là", "có", "cho", "theo", "về", "trong", "được", "các",
    "một", "những", "này", "đó", "với", "từ", "đến", "hoặc", "người",
    "ma", "túy", "pháp", "luật",
}


def load_golden_dataset() -> list[dict]:
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return without_marks.replace("đ", "d")


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[\w]+", strip_accents(text), flags=re.UNICODE)
    return {token for token in tokens if len(token) > 2 and token not in STOPWORDS}


def overlap_score(reference: str, candidate: str) -> float:
    reference_tokens = tokenize(reference)
    if not reference_tokens:
        return 0.0
    candidate_tokens = tokenize(candidate)
    return len(reference_tokens & candidate_tokens) / len(reference_tokens)


def retrieved_context_text(contexts: list[dict]) -> str:
    return "\n\n".join(context.get("content", "") for context in contexts)


def source_recall(expected_sources: list[str], contexts: list[dict]) -> float:
    if not expected_sources:
        return 0.0
    retrieved_sources = {
        context.get("metadata", {}).get("source")
        for context in contexts
        if context.get("metadata", {}).get("source")
    }
    return len(set(expected_sources) & retrieved_sources) / len(set(expected_sources))


def source_precision(expected_sources: list[str], contexts: list[dict]) -> float:
    if not contexts:
        return 0.0
    if not expected_sources:
        return 0.0
    retrieved_sources = [
        context.get("metadata", {}).get("source")
        for context in contexts
        if context.get("metadata", {}).get("source")
    ]
    if not retrieved_sources:
        return 0.0
    useful = sum(1 for source in retrieved_sources if source in expected_sources)
    return useful / len(retrieved_sources)


def make_extractive_answer(contexts: list[dict], max_chars: int = 900) -> str:
    snippets = []
    for context in contexts[:3]:
        content = " ".join(context.get("content", "").split())
        if content:
            snippets.append(content[:300])
    answer = " ".join(snippets)
    return answer[:max_chars] if answer else "I cannot verify this information"


def evaluate_item(item: dict, contexts: list[dict]) -> dict:
    context_text = retrieved_context_text(contexts)
    actual_answer = make_extractive_answer(contexts)

    context_recall = max(
        overlap_score(item["expected_context"], context_text),
        source_recall(item.get("expected_sources", []), contexts),
    )
    context_precision = max(
        source_precision(item.get("expected_sources", []), contexts),
        statistics.mean(
            [overlap_score(item["expected_context"], ctx.get("content", "")) for ctx in contexts]
        )
        if contexts
        else 0.0,
    )

    return {
        "id": item["id"],
        "question": item["question"],
        "category": item.get("category", "unknown"),
        "difficulty": item.get("difficulty", "unknown"),
        "actual_answer": actual_answer,
        "retrieved_sources": [
            ctx.get("metadata", {}).get("source", "unknown") for ctx in contexts
        ],
        "faithfulness": overlap_score(actual_answer, context_text),
        "answer_relevance": overlap_score(item["expected_answer"], actual_answer),
        "context_recall": context_recall,
        "context_precision": context_precision,
    }


def run_config(
    golden_dataset: list[dict],
    config_name: str,
    retrieve_fn: Callable[[str], list[dict]],
) -> dict:
    rows = []
    for item in golden_dataset:
        contexts = retrieve_fn(item["question"])
        rows.append(evaluate_item(item, contexts))

    metrics = ["faithfulness", "answer_relevance", "context_recall", "context_precision"]
    averages = {
        metric: statistics.mean(row[metric] for row in rows) if rows else 0.0
        for metric in metrics
    }
    averages["average"] = statistics.mean(averages.values()) if averages else 0.0

    return {
        "config_name": config_name,
        "averages": averages,
        "rows": rows,
    }


def compare_configs(golden_dataset: list[dict], top_k: int = 5) -> dict:
    configs = {
        "hybrid_rerank": lambda question: retrieve(
            question, top_k=top_k, use_reranking=True
        ),
        "hybrid_no_rerank": lambda question: retrieve(
            question, top_k=top_k, use_reranking=False
        ),
    }

    return {
        name: run_config(golden_dataset, name, retrieve_fn)
        for name, retrieve_fn in configs.items()
    }


def fmt(value: float) -> str:
    return f"{value:.3f}"


def worst_performers(results: dict, limit: int = 3) -> list[dict]:
    rows = results["hybrid_rerank"]["rows"]
    scored = []
    for row in rows:
        avg = statistics.mean(
            [
                row["faithfulness"],
                row["answer_relevance"],
                row["context_recall"],
                row["context_precision"],
            ]
        )
        scored.append({**row, "average": avg})
    return sorted(scored, key=lambda row: row["average"])[:limit]


def export_results(results: dict) -> None:
    a = results["hybrid_rerank"]["averages"]
    b = results["hybrid_no_rerank"]["averages"]
    worst = worst_performers(results)

    lines = [
        "# RAG Evaluation Results",
        "",
        "## Framework sử dụng",
        "",
        "Sử dụng lightweight deterministic evaluator theo phong cách RAGAS/DeepEval: metric được tính bằng token overlap giữa expected answer/context và retrieved context. Cách này chạy local ổn định, không tốn thêm LLM judge quota, và vẫn bao phủ 4 metric bắt buộc.",
        "",
        "## Overall Scores",
        "",
        "| Metric | Config A: hybrid + rerank | Config B: hybrid no rerank | Δ |",
        "|---|---:|---:|---:|",
    ]

    metric_labels = {
        "faithfulness": "Faithfulness",
        "answer_relevance": "Answer Relevance",
        "context_recall": "Context Recall",
        "context_precision": "Context Precision",
        "average": "Average",
    }
    for metric, label in metric_labels.items():
        lines.append(
            f"| {label} | {fmt(a[metric])} | {fmt(b[metric])} | {fmt(a[metric] - b[metric])} |"
        )

    lines.extend(
        [
            "",
            "## A/B Comparison Analysis",
            "",
            "**Config A:** Hybrid retrieval gồm semantic search + BM25, merge bằng RRF và rerank bằng Jina.",
            "",
            "**Config B:** Hybrid retrieval gồm semantic search + BM25, merge bằng RRF nhưng không rerank.",
            "",
            "**Kết luận:** Config có điểm Average cao hơn là cấu hình được khuyến nghị cho demo. Nếu Config A tốt hơn, reranking giúp đưa context liên quan lên đầu; nếu Config B tốt hơn hoặc tương đương, có thể ưu tiên B khi cần giảm chi phí API.",
            "",
            "## Worst Performers (Bottom 3 - Config A)",
            "",
            "| # | Question | Faithfulness | Relevance | Recall | Precision | Retrieved Sources |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )

    for row in worst:
        sources = ", ".join(row["retrieved_sources"][:5])
        question = row["question"].replace("|", "\\|")
        lines.append(
            f"| {row['id']} | {question} | {fmt(row['faithfulness'])} | "
            f"{fmt(row['answer_relevance'])} | {fmt(row['context_recall'])} | "
            f"{fmt(row['context_precision'])} | {sources} |"
        )

    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "### Cải tiến 1",
            "**Action:** Bổ sung thêm văn bản pháp luật còn thiếu nếu golden dataset mở rộng sang các nghị định/danh mục chưa có trong corpus.  ",
            "**Expected impact:** Tăng context recall cho các câu hỏi pháp luật chuyên sâu.",
            "",
            "### Cải tiến 2",
            "**Action:** Chuẩn hóa và làm giàu metadata source, ví dụ tên văn bản, số điều, ngày bài báo.  ",
            "**Expected impact:** Citation đẹp hơn và context precision dễ phân tích hơn.",
            "",
            "### Cải tiến 3",
            "**Action:** Điều chỉnh top_k và ngưỡng fallback PageIndex cho các câu hỏi khó.  ",
            "**Expected impact:** Giảm nguy cơ thiếu evidence khi câu hỏi cần nhiều đoạn chứng cứ.",
            "",
        ]
    )

    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    golden_dataset = load_golden_dataset()
    print(f"Loaded {len(golden_dataset)} golden test cases")
    results = compare_configs(golden_dataset, top_k=args.top_k)
    export_results(results)
    print(f"Saved results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
