# Data statement: Synthetic Kenyan-style investor corpus (large)

Version 2.0 | seed 2026 | scale 1 | fictional as-of date 2026-09-30 | generated 2026-10-31 | content hash a9fcbbf6eaac17db

## 1. Purpose
To test the RAG pipeline (retrieval, three-tier trust labelling, conflict handling, refusal and advice guardrails) at a
volume the author could not collect from real sources. It is **not** evidence about real markets, and results on it must
never be reported as real-world accuracy.

## 2. Composition
195 documents, 339 pages, about 22,472 words. Tier 1: 78, Tier 2: 81, Tier 3: 36.
Document types: investor guides, FAQs, fund factsheets, company listing summaries (Tier 1); explainers, stale articles,
fund comparisons, analyst notes, weekly market wraps (Tier 2); commentator columns, blog and forum posts (Tier 3).
Topics: Treasury bills and bonds, money market and other funds, shares, REITs, tax, SACCOs, retirement schemes, a small-ticket savings bond.
Evaluation questions: 174 (advice: 20, conflict: 34, market_data: 12, official_fact: 66, opinion: 18, out_of_corpus: 24).

## 3. Ground truth by design
Documents and questions come from one fact table, so the gold answer and the expected source are known by construction.
Planted situations: official rules that Tier 3 posts contradict (conflict), outdated Tier 2 articles quoting old
figures (conflict, stale), fund and company hype posts that overstate official numbers, out-of-scope questions with
terms absent from the corpus, and advice-seeking questions that must be refused. `--check` verifies that every gold
answer appears in its expected source and that no out-of-corpus term occurs anywhere.

## 4. Why it cannot pass as fact
All organisations, funds, companies and commentators are fictional and marked SYN; amounts are in "SYN Sh"; figures are
invented and deliberately differ from real Kenyan rules; no real person, company, regulator or quotation is used; every
document ends with a synthetic-data footer; the validator rejects a list of real names; URLs use the synthetic:// scheme.

## 5. Separation from real data
Every record carries `"synthetic": true`. Ingest into its own collection (`kenya_syn_large`), never into the real
collection, and report its scores in a separate table.

## 6. Reproducibility
`python scripts/build_synthetic_large.py --seed 2026 --scale 1` regenerates identical files (hash above).
Changing the seed gives a different but equally valid dataset, which can be used to check that results are stable.

## 7. Limitations and bias
- One author (the generator) wrote every document, so style is uniform and templated; real text is messier.
- Each fact is stated in few paraphrases, so retrieval is easier than on real documents.
- Tier 3 posts are exaggerated by design and easy to spot; real misinformation is subtler.
- Dates, amounts and names are invented; there is no real temporal drift.
- Questions are generated from the same templates as the documents, so scores are optimistic. Treat them as a
  regression and pipeline check, and report the real-corpus tests (section D of the test log) as the evidence of usefulness.
- Out-of-corpus questions test refusal only in the narrow sense that their key terms are absent.

References for the documentation practice: Gebru et al., "Datasheets for Datasets" (2021); Bender and Friedman, "Data Statements for NLP" (2018). Verify the citations before use.
