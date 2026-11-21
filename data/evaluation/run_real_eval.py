"""Rebuild the two-document real evaluation collection and run its fixed question set."""
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
os.environ['REAL_DIR'] = str(ROOT / 'data' / 'evaluation' / 'real_eval_sources')
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from ingest import ingest_real  # noqa: E402

inserted = ingest_real(reset=True)
print(f'Indexed {inserted} chunks from the evaluation sample into kenya_real.')
config.OPENAI_API_KEY = ''  # local extractive generation; no external LLM calls
sys.argv = [
    'evaluate_real.py',
    '--questions', str(ROOT / 'data' / 'evaluation' / 'real_questions.jsonl'),
    '--output', str(ROOT / 'data' / 'evaluation' / 'real_results.json'),
    '--report', str(ROOT / 'data' / 'evaluation' / 'real_report.json'),
    '--collection', config.COLLECTION_REAL,
]
from evaluate_real import main  # noqa: E402
main()

questions = [json.loads(line) for line in (ROOT / 'data/evaluation/real_questions.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
results = json.loads((ROOT / 'data/evaluation/real_results.json').read_text(encoding='utf-8'))
expected = {q['id']: set(q.get('relevant_source_ids', [])) for q in questions}
scored = [r for r in results if expected.get(r['id'])]
precision = [len(set(r.get('cited_source_ids', [])) & expected[r['id']]) / max(1, len(set(r.get('cited_source_ids', [])))) for r in scored]
recall = [len(set(r.get('cited_source_ids', [])) & expected[r['id']]) / len(expected[r['id']]) for r in scored]
report_path = ROOT / 'data/evaluation/real_report.json'
report = json.loads(report_path.read_text(encoding='utf-8'))
report['citation_metrics'] = {
    'n': len(scored),
    'citation_precision': round(sum(precision) / len(precision), 3),
    'citation_recall': round(sum(recall) / len(recall), 3),
}
report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('Citation metrics:', json.dumps(report['citation_metrics']))
