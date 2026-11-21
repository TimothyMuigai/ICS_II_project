"""Synthetic evaluation. Reads eval_questions.csv written by build_synthetic_large.py."""
from __future__ import annotations
import argparse
import csv
import json
import time
from pathlib import Path

from config import SYNTHETIC_DIR, COLLECTION_SYN
from pipeline import answer_question


# ---------------------------------------------------------------- metrics

def precision_at_k(retrieved, relevant, k):
    if not relevant:
        return None
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(x in relevant for x in top) / len(top)


def recall_at_k(retrieved, relevant, k):
    if not relevant:
        return None
    return sum(x in relevant for x in retrieved[:k]) / len(relevant)


def reciprocal_rank(retrieved, relevant):
    for i, sid in enumerate(retrieved, start=1):
        if sid in relevant:
            return 1.0 / i
    return 0.0


def citation_precision(cited, relevant):
    if not cited:
        return 0.0
    return sum(x in relevant for x in cited) / len(cited)


def citation_recall(cited, relevant):
    if not relevant:
        return None
    return sum(x in cited for x in relevant) / len(relevant)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(SYNTHETIC_DIR / "eval_questions.csv"))
    ap.add_argument("--output", default="data/evaluation/synthetic_results.json")
    ap.add_argument("--collection", default=COLLECTION_SYN)
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None,
                    help="Only evaluate the first N questions (smoke test)")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="Seconds between questions (Groq free tier: 2.5)")
    args = ap.parse_args()

    with open(args.questions, encoding="utf-8") as f:
        questions = list(csv.DictReader(f))

    if args.limit:
        questions = questions[:args.limit]

    total = len(questions)
    print(f"Evaluating {total} questions  (sleep={args.sleep}s between calls)")
    if args.sleep > 0:
        print(f"  Expected duration: ~{(total * args.sleep) / 60:.1f} min + LLM time")

    results = []
    dirty = 0
    t0 = time.time()

    for i, q in enumerate(questions, 1):
        relevant = {s for s in q["expected_source_ids"].split(";") if s}
        rag = answer_question(q["question"], collection=args.collection)

        if "(LLM failed:" in rag.get("answer", ""):
            dirty += 1

        results.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "gold_answer": q["gold_answer"],
            "expected_source_ids": sorted(relevant),
            "precision_at_k": precision_at_k(rag["retrieved_source_ids"], relevant, args.k),
            "recall_at_k": recall_at_k(rag["retrieved_source_ids"], relevant, args.k),
            "mrr": reciprocal_rank(rag["retrieved_source_ids"], relevant),
            "citation_precision": citation_precision(rag["cited_source_ids"], relevant),
            "citation_recall": citation_recall(rag["cited_source_ids"], relevant),
            "answer": rag["answer"],
            "retrieved_source_ids": rag["retrieved_source_ids"],
            "cited_source_ids": rag["cited_source_ids"],
            "abstained": rag["abstained"],
        })

        if args.sleep > 0 and i < total:
            time.sleep(args.sleep)

        if i % 10 == 0 or i == total:
            elapsed = time.time() - t0
            eta = (elapsed / i) * (total - i) if i else 0
            print(f"  {i:3d}/{total}  elapsed={elapsed:5.0f}s  eta={eta:5.0f}s  fallbacks={dirty}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None

    print(f"\nwrote {len(results)} rows -> {out}")
    print(f"  P@{args.k}  = {mean([r['precision_at_k'] for r in results])}")
    print(f"  R@{args.k}  = {mean([r['recall_at_k'] for r in results])}")
    print(f"  MRR    = {mean([r['mrr'] for r in results])}")
    print(f"  cite P = {mean([r['citation_precision'] for r in results])}")
    print(f"  cite R = {mean([r['citation_recall'] for r in results])}")

    if dirty:
        print(f"\n⚠️  {dirty}/{total} fell back to extractive (LLM errors).")
        print(f"   Re-run with --sleep 3.0 to reduce rate-limit hits.")
    else:
        print(f"\n✅ Clean run: 0 fallbacks. All answers used the LLM.")


if __name__ == "__main__":
    main()