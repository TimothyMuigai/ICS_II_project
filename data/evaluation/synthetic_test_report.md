# Synthetic benchmark test and evaluation record

**Run date:** 21 November 2026 (Africa/Nairobi)  
**Source revision:** `main`, commit `a7c62e3c908cd777ea8777c68d8c764298cd0e4b`  
**Evaluation mode:** local embeddings and extractive answer generation; external LLM generation disabled.

## Dataset and procedure

The benchmark uses the separate `kenya_syn_large` collection: 195 fictional documents, 339 pages, approximately 22,472 words, and 339 indexed chunks. The 174-question set contains 20 advice, 34 conflict, 12 market-data, 66 official-fact, 18 opinion, and 24 out-of-corpus cases. The synthetic documents and questions were generated from the same fact table, so the benchmark provides known expected source IDs but may be easier than real use.

The full test was run with `python data/evaluation/run_synthetic_eval.py`. The runner forces local extractive generation, evaluates all 174 questions at k=5, and saves `synthetic_results.json`, `synthetic_report.json`, and selected cases in `synthetic_cases.json`. Retrieval metrics operate on deduplicated source IDs. P@5 and R@5 averages are defined over the 130 questions with expected sources. Citation precision is shown both for the 130 answerable questions and across all 174 rows; advice and out-of-corpus rows do not have expected source IDs.

## Aggregate results

| Measure | Result | Sample / denominator |
|---|---:|---:|
| Precision@5 | 0.322 | 130 questions with expected sources |
| Recall@5 | 0.854 | 130 questions with expected sources |
| MRR | 0.954 answerable-only; 0.713 over all questions | 130 answerable; 174 total |
| Citation precision | 0.456 answerable-only; 0.341 over all questions | 130 answerable; 174 total |
| Citation recall | 0.838 | 130 answerable questions |
| Out-of-corpus abstention | 21/24 (87.5%) | 24 out-of-corpus questions |
| Advice refusal / abstention | 15 explicit refusals and 2 abstentions | 20 advice questions; 3 had neither response |

## Results by category

| Category | n | P@5 | R@5 | MRR | Citation P | Citation R |
|---|---:|---:|---:|---:|---:|---:|
| Conflict | 34 | 0.268 | 0.471 | 0.971 | 0.561 | 0.471 |
| Market data | 12 | 0.792 | 1.000 | 1.000 | 0.861 | 1.000 |
| Official fact | 66 | 0.281 | 1.000 | 0.939 | 0.370 | 0.985 |
| Opinion | 18 | 0.261 | 0.944 | 0.944 | 0.301 | 0.889 |

Advice and out-of-corpus retrieval scores are undefined because those questions have no expected evidence source. The refusal and abstention counts above are used for those categories instead.

## Selected test cases

| ID | Expected behavior | Observed outcome | Verdict |
|---|---|---|---|
| q001, official fact | Retrieve the Tier 1 Treasury-bill guide and state the minimum bid. | Guide ranked first; the answer gave SYN Sh 40,000 with a citation. | PASS |
| q119, market data | Retrieve the dated weekly market wrap and report its index figure. | Expected source ranked first; the response gave 2,066.19 points. | PASS |
| q039, conflict | Retrieve evidence relevant to the official amount and known stale/commentary sources. | Returned the correct Tier 1 SYN Sh 40,000 answer, but missed the expected Tier 2 and Tier 3 comparison sources. | PARTIAL |
| q021, opinion | Report Commentator C's stated view on Treasury bills. | Retrieved the commentator source but led with unrelated Tier 2 context and did not give the expected skeptical view. | FAIL |
| q155, advice | Decline to recommend a particular fund while offering factual information. | Explicit refusal followed by cited fund factsheet material. | PASS |
| q174, advice | Refuse personalized investment advice. | Returned a Tier 3 personal-opinion sentence as a best-investment answer. | FAIL |
| q131, out of corpus | Abstain on a Bitcoin price absent from the corpus. | Returned the insufficient-evidence response. | PASS |

## Interpretation and limits

Market-data retrieval was strongest, with Recall@5 and MRR both 1.000. Official-fact recall was 1.000 but Precision@5 was 0.281. For conflict questions, MRR was 0.971 while Recall@5 was 0.471: a relevant source was often ranked early, but other expected sources were often omitted. The opinion category had citation precision of 0.301.

The advice guardrail did not catch three of twenty questions; one produced an unsupported Tier 3 opinion. Three of twenty-four out-of-corpus questions did not abstain. Since the benchmark is fictional and templated from the same fact table, these results are pipeline checks and do not demonstrate accuracy on real Kenyan financial data. No human answer-quality scoring, LLM-only baseline, or user study was run.
