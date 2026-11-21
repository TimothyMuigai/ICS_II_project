"""Real-world evaluation. Reads data/evaluation/real_questions.jsonl."""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path

from config import COLLECTION_REAL
from pipeline import answer_question


def _load_jsonl(p: str | Path) -> list[dict]:
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def recall_at_k(retrieved, relevant, k):
    if not relevant: return None
    return sum(x in relevant for x in retrieved[:k]) / len(relevant)


def precision_at_k(retrieved, relevant, k):
    if not relevant: return None
    top = retrieved[:k]
    return sum(x in relevant for x in top) / len(top) if top else 0.0


def mrr(retrieved, relevant):
    for i, sid in enumerate(retrieved, start=1):
        if sid in relevant: return 1.0 / i
    return 0.0


def evaluate_one(q, rag, k=5):
    relevant = set(q.get("relevant_source_ids", []))
    must_abstain = bool(q.get("must_abstain", False))
    abstained = bool(rag.get("abstained", False))
    abst_ok = ("yes" if abstained else "no") if must_abstain else ("no" if abstained else "yes")
    return {
        "id": q["id"], "category": q["category"],
        "precision_at_k": precision_at_k(rag["retrieved_source_ids"], relevant, k),
        "recall_at_k": recall_at_k(rag["retrieved_source_ids"], relevant, k),
        "mrr": mrr(rag["retrieved_source_ids"], relevant),
        "answer": rag["answer"],
        "retrieved_source_ids": rag["retrieved_source_ids"],
        "cited_source_ids": rag["cited_source_ids"],
        "abstained": abstained,
        "must_abstain": must_abstain,
        "abstention_correct": abst_ok,
    }


def aggregate(rows):
    by = defaultdict(list)
    for r in rows: by[r["category"]].append(r)

    def _mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None

    def summarize(group):
        return {
            "n": len(group),
            "precision_at_k": _mean([r["precision_at_k"] for r in group]),
            "recall_at_k": _mean([r["recall_at_k"] for r in group]),
            "mrr": _mean([r["mrr"] for r in group]),
            "abstention_accuracy": round(
                sum(r["abstention_correct"] == "yes" for r in group) / len(group), 3
            ) if group else None,
        }
    return {"overall": summarize(rows), "by_category": {c: summarize(g) for c, g in sorted(by.items())}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="data/evaluation/real_questions.jsonl")
    ap.add_argument("--output", default="data/evaluation/real_results.json")
    ap.add_argument("--report", default="data/evaluation/real_report.json")
    ap.add_argument("--collection", default=COLLECTION_REAL)
    args = ap.parse_args()

    questions = _load_jsonl(args.questions)
    results = [evaluate_one(q, answer_question(q["question"], collection=args.collection)) for q in questions]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    report = aggregate(results)
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(results)} results -> {args.output}")
    print(json.dumps(report["overall"], indent=2))


if __name__ == "__main__":
    main()