# Real-data test and evaluation record

**Run date:** 18 November 2026 (Africa/Nairobi)  
**Source revision:** `main`, commit `a7c62e3c908cd777ea8777c68d8c764298cd0e4b`  
**Evaluation mode:** local embeddings and extractive answer generation; external LLM calls disabled.

## Evaluation corpus and evidence

The pilot indexes two official CMA brochures copied from `data/real/CMA/CMA_info_data/` into `real_eval_sources/`:

- `CMA-Beginners-guide.pdf` (2 pages)
- `Investor-Protection.pdf` (3 pages)

The importer produced 13 chunks in the `kenya_real` collection. Four questions have reference source IDs and answer statements checked against the source pages; one question is deliberately outside the corpus. The exact cases and evidence locators are in `real_questions.jsonl`. `real_results.json` and `real_report.json` preserve the evaluator output.

The complete project corpus was not indexed for this pilot. The question set is small and limited to two CMA brochures, so results are an implementation check, not a representative estimate of financial question-answering accuracy.

## Repeatable commands

From the repository root in PowerShell:

```powershell
python -m pip install -r requirements.txt -r requirements-service.txt
python data/evaluation/run_real_eval.py
```

`run_real_eval.py` sets `REAL_DIR` to the pilot sample and rebuilds `kenya_real` before scoring. It therefore replaces the current real collection with these two documents. The sample inputs and question set remain unchanged. The runner clears the configured model key in-process so evaluation uses the local extractive fallback and does not call an external generation API.

For the HTTP-style checks, install the service dependencies and HTTPX with `python -m pip install -r requirements-service.txt httpx`, then run `real_api_smoke.py` with the project environment. The recorded run used FastAPI 0.165.0, Starlette 1.10.0, Pydantic 2.14.3, and HTTPX 0.28.1 installed in a temporary project-local target directory.

## Retrieval and abstention results

On the four in-corpus questions, the saved evaluator reported source-level metrics over deduplicated source IDs (at most two distinct sources in this pilot):

| Measure | Result | Sample |
|---|---:|---:|
| Source-level Precision@5 | 0.375 | 4 answerable questions |
| Recall@5 | 0.750 | 4 answerable questions |
| MRR | 0.500 | 4 answerable questions |
| Citation precision | 0.375 | 4 answerable questions; computed in run_real_eval.py from cited and expected source IDs |
| Citation recall | 0.750 | 4 answerable questions; computed in run_real_eval.py from cited and expected source IDs |
| Abstention accuracy | 1.000 | 5 total questions; the out-of-corpus question abstained and the four answerable questions did not |

MRR across all five rows, including the out-of-corpus case, is 0.400. Strict end-to-end review of answer content plus source attribution found 2 of 4 answerable questions fully successful, one partial result, and one failure. Counting the correct out-of-corpus abstention, the set has 3 full passes, 1 partial result, and 1 failure.

The expected source was retrieved and cited on three of four answerable questions. The partial result answered the adviser-licensing question correctly but cited `Investor-Protection` instead of the named `CMA-Beginners-guide`. The failure retrieved the compensation-fund source but the extractive answer selected unrelated sentences and did not state the fund's purpose. The CDS and CMA-regulatory-role questions returned correct evidence. The out-of-corpus S&P 500 question abstained.

## API smoke-test results

The FastAPI app was exercised with its in-process `TestClient`; this is not a public or network-hosted deployment.

| Check | Expected | Observed | Verdict |
|---|---|---|---|
| `GET /health` | HTTP 200 and healthy status | HTTP 200; status `ok`; 13 real chunks | PASS |
| `POST /query` with the CDS question | HTTP 200 and source citation | HTTP 200; cited `CMA-Beginners-guide`; 5,426 ms in the recorded run | PASS |
| Empty question | HTTP 400 | HTTP 400 | PASS |
| Question longer than 4,000 characters | HTTP 400 | HTTP 400 | PASS |

The API response included five chunk-level citation entries with repeated source IDs, so source-level citation deduplication remains a usability improvement.

## Test environment and limitations

The run used Windows 11, CPython 3.14.0 (AMD64), Node.js 24.11.1, ChromaDB 1.5.9, sentence-transformers 6.2.0, pypdf 6.21.4, and the cached `sentence-transformers/all-MiniLM-L6-v2` embedding model. PyTorch reported no CUDA device; the reported evaluation used CPU inference. FastAPI dependencies were installed temporarily for the smoke test. The OpenAI Python SDK was not installed, and no external LLM generation was evaluated.

PDF extraction emitted warnings that `fontTools` was unavailable for some embedded fonts. Extracted text contained replacement characters in a few passages. The real corpus also contains CBK and NSE files that were not included in this pilot; the current real ingestion code does not ingest CSV files.

The app was tested in-process using `TestClient`; the frontend was not launched, and no public deployment, user study, repeated latency trial, answer-judge assessment, or LLM-only baseline was performed. The Git remote is configured, but access permissions, supervisor access, a release tag, and a hosted deployment were not verified. Test artifacts were not committed to the source branch during this work.



