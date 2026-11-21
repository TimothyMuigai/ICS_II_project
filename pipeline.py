# pipeline.py
"""answer_question() — the one function the rest of the system uses."""
from __future__ import annotations
from typing import Any

from config import COLLECTION_SYN, COLLECTION_REAL
from retriever import retrieve, best_source_ids
from generator import generate

# Threshold below which we refuse rather than answer.
# Minimum RAW similarity (before tier/recency fusion) to consider evidence usable.
# Empirically: real matches ~0.55+, weak matches ~0.30-0.40, junk ~0.15-0.25.
MIN_RAW_SIMILARITY = 0.40


def answer_question(
    question: str,
    collection: str = COLLECTION_SYN,
    min_similarity: float = MIN_RAW_SIMILARITY,
) -> dict[str, Any]:
    """Return the standard RAG result dict."""
    evidence = retrieve(collection, question)
    retrieved = best_source_ids(evidence)

    # Abstain if there is no evidence at all, OR if the best raw similarity
    # (not the fused tier/recency score) is below the threshold.
    top_raw_sim = max((e["similarity"] for e in evidence), default=0.0)
    if not evidence or top_raw_sim < min_similarity:
        return {
            "answer": "I don't have enough evidence in the provided documents to answer this.",
            "retrieved_source_ids": retrieved,
            "cited_source_ids": [],
            "abstained": True,
            "evidence": [],
        }

    out = generate(question, evidence)
    return {
        "answer": out["answer"],
        "retrieved_source_ids": retrieved,
        "cited_source_ids": out["cited_source_ids"],
        "abstained": out["abstained"],
        "evidence": evidence,
    }