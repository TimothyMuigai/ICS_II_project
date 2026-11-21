"""Show 3 official_fact answers that have empty cited_source_ids."""
import json

rs = json.load(open("data/evaluation/synthetic_results.json", encoding="utf-8"))
fails = [r for r in rs if r["category"] == "official_fact" and not r["cited_source_ids"]]

print(f"official_fact failures: {len(fails)}/{sum(1 for r in rs if r['category']=='official_fact')}\n")
for r in fails[:3]:
    print("=" * 70)
    print(f"QID:       {r['id']}")
    print(f"Question:  {r['question']}")
    print(f"Abstained: {r['abstained']}")
    print(f"Retrieved: {r['retrieved_source_ids'][:3]}")
    print(f"LLM answer:")
    print(f"  {r['answer'][:600]}")
    print()