"""Show rows where citation_precision is 0 or 0.5, to see WHY."""
import json

rs = json.load(open("data/evaluation/smoke_results.json", encoding="utf-8"))
low_p = [r for r in rs if r["citation_precision"] is not None and r["citation_precision"] < 0.99]

print(f"low citation-precision rows: {len(low_p)}/{len(rs)}\n")
for r in low_p[:5]:
    print("=" * 70)
    print(f"QID: {r['id']}  |  P={r['citation_precision']}  R={r['citation_recall']}")
    print(f"Question:  {r['question']}")
    print(f"Expected:  {r['expected_source_ids']}")
    print(f"Cited:     {r['cited_source_ids']}")
    extra = [c for c in r["cited_source_ids"] if c not in r["expected_source_ids"]]
    print(f"Extra:     {extra}")
    print()