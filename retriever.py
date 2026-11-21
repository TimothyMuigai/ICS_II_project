# retriever.py
"""Intent-aware, author-aware, date-aware retrieval."""
from __future__ import annotations
import re
from datetime import date
from typing import Any

from config import TOP_K, RERANK_K
from embedder import embed_query
from store import query as chroma_query


TIER_WEIGHT_FACTUAL = {1: 1.0, 2: 0.7, 3: 0.35}
TIER_WEIGHT_OPINION = {1: 0.5, 2: 0.75, 3: 1.0}

_OPINION_PATTERNS = (
    r"\bwhat (does|did) .{1,40} (say|think|argue|claim|write|state|believe)\b",
    r"\baccording to\b",
    r"\b(commentator|analyst|blogger|columnist)\b",
    r"\bopinion\b",
    r"\bview(s)? of\b",
    r"\bwhat is .{1,30} (position|stance|view)\b",
)

_DATE_IN_QUERY = re.compile(
    r"\b(20\d{2}-\d{2}-\d{2}|(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+20\d{2})\b",
    re.IGNORECASE,
)

# Lightweight topic inference — used only to cancel wrong-author boosts.
_TOPIC_HINTS = {
    "tbills": ("treasury bill", "t-bill", "tbills"),
    "tbonds": ("treasury bond", "t-bond"),
    "mmf": ("money market fund", "mmf"),
    "equities": ("share", "equity", "stock", "listing"),
    "reits": ("reit", "real estate investment trust"),
    "tax": ("tax", "withholding"),
    "saccos": ("sacco", "savings and credit"),
    "pensions": ("pension", "retirement"),
    "savings_bond": ("sokoni", "savings bond"),
}

def _doc_type_boost(doc_type: str, opinion: bool) -> float:
    if not opinion:
        return 1.0
    if doc_type == "commentary":
        return 1.4
    if doc_type == "social_post":
        return 0.6
    return 1.0

def is_opinion_question(question: str) -> bool:
    q = question.lower()
    return any(re.search(p, q) for p in _OPINION_PATTERNS)


def _has_date_in_query(question: str) -> bool:
    return bool(_DATE_IN_QUERY.search(question))


def _infer_topic(question: str) -> str:
    q = question.lower()
    for topic, hints in _TOPIC_HINTS.items():
        if any(h in q for h in hints):
            return topic
    return ""


def _recency_factor(published: str, disable: bool = False) -> float:
    if disable or not published:
        return 1.0
    try:
        y, m, d = (int(x) for x in published.split("-"))
        age_days = (date.today() - date(y, m, d)).days
    except Exception:
        return 1.0
    return max(0.6, min(1.0, 0.5 ** (age_days / 730)))


def _date_match_boost(published: str, question: str) -> float:
    m = _DATE_IN_QUERY.search(question)
    if not m or not published:
        return 1.0
    return 1.5 if m.group(1).lower() in published.lower() else 1.0


def _author_match_boost(author: str, question: str) -> float:
    if not author:
        return 1.0
    core = author.replace(" (SYN)", "").strip().lower()
    if core and core in question.lower():
        return 1.6
    parts = core.split()
    if len(parts) >= 2 and " ".join(parts[:2]) in question.lower():
        return 1.6
    return 1.0


def retrieve(collection: str, question: str, k: int = TOP_K) -> list[dict[str, Any]]:
    emb = embed_query(question)

    opinion = is_opinion_question(question)
    date_match = _DATE_IN_QUERY.search(question)
    topic_in_q = _infer_topic(question)
    weights = TIER_WEIGHT_OPINION if opinion else TIER_WEIGHT_FACTUAL

    # If a specific date is in the question, restrict the candidate pool
    # to chunks whose published_date matches. Fall back to unfiltered if empty.
    raw = None
    if date_match:
        raw = chroma_query(
            collection, emb, n=k * 3,
            where={"published_date": {"$eq": date_match.group(1)}},
        )
        if not raw or not raw.get("ids") or not raw["ids"][0]:
            raw = None
    if raw is None:
        raw = chroma_query(collection, emb, n=k * 3)

    if not raw or not raw.get("documents") or not raw["documents"][0]:
        return []

    date_specific = date_match is not None
    results = []
    for doc_id, text, meta, dist in zip(
        raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    ):
        sim = 1.0 - float(dist)
        tier = int(meta.get("tier", 2))
        published = meta.get("published_date", "")
        author = meta.get("author", "")

        author_boost = _author_match_boost(author, question)
        # Cancel the author boost if the topic doesn't match the question.
        if author_boost > 1.0 and topic_in_q and meta.get("topic") and meta["topic"] != topic_in_q:
            author_boost = 1.0

        score = (
            sim
            * weights.get(tier, 0.6)
            * _recency_factor(published, disable=date_specific)
            * _date_match_boost(published, question)
            * author_boost
        )
        results.append({
            "chunk_id": doc_id,
            "source_id": meta.get("source_id"),
            "text": text,
            "tier": tier,
            "published_date": published,
            "author": author,
            "topic": meta.get("topic", ""),
            "doc_type": meta.get("doc_type", ""),
            "page": meta.get("page", 0),
            "similarity": sim,
            "score": score,
        })

    results.sort(key=lambda r: r["score"], reverse=True)

    if opinion:
        t3_in_topk = any(r["tier"] == 3 for r in results[:RERANK_K])
        if not t3_in_topk:
            best_t3 = next((r for r in results if r["tier"] == 3 and r["similarity"] >= 0.55), None)
            if best_t3:
                results = results[:RERANK_K - 1] + [best_t3]

    return results[:RERANK_K]


def best_source_ids(results: list[dict[str, Any]]) -> list[str]:
    seen, out = set(), []
    for r in results:
        sid = r["source_id"]
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out