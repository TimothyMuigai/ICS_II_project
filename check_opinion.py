"""Does the opinion source exist in ChromaDB, and can retrieval find it?"""
import json
import csv
from pathlib import Path
from store import get_collection, query
from embedder import embed_query
from retriever import retrieve


COLL = "kenya_syn_large"
col = get_collection(COLL)

# 1. Do the opinion sources exist at all?
q_rows = list(csv.DictReader(open("data/synthetic_large/eval_questions.csv", encoding="utf-8")))
opinion = [q for q in q_rows if q["category"] == "opinion"]
print(f"opinion questions: {len(opinion)}")

expected_ids = {s for q in opinion for s in q["expected_source_ids"].split(";") if s}
print(f"expected opinion source_ids: {sorted(expected_ids)[:5]} ...")

# 2. Are those source_ids actually present in ChromaDB metadata?
all_meta = col.get(limit=10000, include=["metadatas"])["metadatas"]
live_ids = {m["source_id"] for m in all_meta}
missing = expected_ids - live_ids
print(f"expected: {len(expected_ids)}  live in chroma: {len(expected_ids - missing)}  missing: {len(missing)}")
if missing:
    print(f"MISSING source_ids (first 5): {sorted(missing)[:5]}")

# 3. For one failing question, what does raw retrieval actually rank?
q = opinion[0]
print(f"\n--- {q['id']}: {q['question']} ---")
print(f"expected: {q['expected_source_ids']}")
emb = embed_query(q["question"])
raw = query(COLL, emb, n=20)
hits = list(zip(raw["ids"][0], raw["metadatas"][0], raw["distances"][0]))
print("top 20 raw hits (source_id, tier, similarity):")
for cid, meta, dist in hits:
    print(f"  {meta['source_id']:45s} tier={meta['tier']} sim={1-dist:.3f}")

# 4. What does the retriever's rerank produce?
print("\nretriever output (post-rerank, top 5):")
for e in retrieve(COLL, q["question"]):
    print(f"  {e['source_id']:45s} tier={e['tier']} score={e['score']:.3f} sim={e['similarity']:.3f}")