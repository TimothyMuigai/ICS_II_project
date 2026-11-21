"""Show the 15 questions with the worst retrieval MRR."""
import json

rows = json.load(open("data/evaluation/synthetic_results.json", encoding="utf-8"))
rows.sort(key=lambda r: r["mrr"])

print(f"{'id':8s} {'MRR':>5s} {'R@5':>5s} {'cat':20s} {'retrieved':30s} question")
print("-" * 120)
for r in rows[:15]:
    got = ",".join(r["retrieved_source_ids"][:2])
    r5 = r["recall_at_k"] if r["recall_at_k"] is not None else 0.0
    print(f"{r['id']:8s} {r['mrr']:5.2f} {r5:5.2f} {r['category']:20s} {got:30s} {r['question'][:60]}")