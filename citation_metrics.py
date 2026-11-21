"""Compute citation precision and recall, overall and per category."""
import json
from collections import defaultdict

rs = json.load(open("data/evaluation/synthetic_results.json", encoding="utf-8"))


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def cite_p(cited, expected):
    if not cited:
        return 0.0
    return sum(s in expected for s in cited) / len(cited)


def cite_r(cited, expected):
    if not expected:
        return None
    return sum(s in cited for s in expected) / len(expected)


# Compute directly from cited_source_ids so it works even on the OLD json
for r in rs:
    expected = set(r.get("expected_source_ids", []))
    r["citation_precision"] = cite_p(r["cited_source_ids"], expected)
    r["citation_recall"] = cite_r(r["cited_source_ids"], expected)

print("Overall:")
print(f"  citation_precision = {mean([r['citation_precision'] for r in rs])}")
print(f"  citation_recall    = {mean([r['citation_recall'] for r in rs])}")

by_cat = defaultdict(list)
for r in rs:
    by_cat[r["category"]].append(r)

print("\nPer category:")
print(f"  {'category':20s}  {'P':>6s}  {'R':>6s}  {'n':>4s}  {'cited?':>7s}")
for cat in sorted(by_cat):
    rows = by_cat[cat]
    with_cites = sum(1 for r in rows if r["cited_source_ids"])
    print(f"  {cat:20s}  {str(mean([r['citation_precision'] for r in rows])):>6s}  "
          f"{str(mean([r['citation_recall'] for r in rows])):>6s}  {len(rows):>4d}  "
          f"{with_cites:>4d}/{len(rows):<3d}")