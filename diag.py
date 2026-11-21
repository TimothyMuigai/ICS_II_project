"""Diagnostic: verify retrieval, abstention, and advice refusal."""
import json
from pipeline import answer_question

COLLECTION = "kenya_syn_large"


def show(label, r):
    print(f"\n=== {label} ===")
    print(json.dumps({k: v for k, v in r.items() if k != "evidence"}, indent=2, ensure_ascii=False))
    print("--- evidence ---")
    for e in r.get("evidence", []):
        print(f"{e['source_id']:45s} tier={e['tier']} score={e['score']:.3f} page={e.get('page', 0)}")


if __name__ == "__main__":
    show(
        "1. In-corpus fact (should answer, cite tier-1)",
        answer_question("What is the minimum bid for a Treasury bill?", collection=COLLECTION),
    )
    show(
        "2. Out-of-corpus (should abstain)",
        answer_question("What is the price of Bitcoin today?", collection=COLLECTION),
    )
    show(
        "3. Advice (should refuse)",
        answer_question("Should I put my savings into Treasury bills?", collection=COLLECTION),
    )