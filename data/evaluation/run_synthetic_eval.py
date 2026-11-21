"""Run the full synthetic benchmark locally and save reproducible summaries."""
from pathlib import Path
import builtins
import collections
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
config.OPENAI_API_KEY = ''  # use the local extractive generator only
sys.stdout.reconfigure(encoding='utf-8')
sys.argv = [
    'evaluate.py',
    '--questions', str(ROOT / 'data/synthetic_large/eval_questions.csv'),
    '--output', str(ROOT / 'data/evaluation/synthetic_results.json'),
    '--collection', config.COLLECTION_SYN,
    '-k', '5',
]
import evaluate  # noqa: E402

def truthful_print(*args, **kwargs):
    message = ' '.join(str(x) for x in args)
    if 'Clean run: 0 fallbacks.' in message:
        message = 'Local extractive run completed; external LLM generation was disabled.'
    builtins.print(message, **kwargs)

evaluate.print = truthful_print
evaluate.main()

rows = json.loads((ROOT / 'data/evaluation/synthetic_results.json').read_text(encoding='utf-8'))
groups = collections.defaultdict(list)
for row in rows:
    groups[row['category']].append(row)

def mean(values):
    values = [x for x in values if x is not None]
    return round(sum(values) / len(values), 3) if values else None

by_category = {}
for category, group in sorted(groups.items()):
    answerable = [x for x in group if x['expected_source_ids']]
    refusals = sum("I can't recommend a specific investment" in x['answer'] for x in group)
    by_category[category] = {
        'n': len(group),
        'precision_at_5': mean([x['precision_at_k'] for x in group]),
        'recall_at_5': mean([x['recall_at_k'] for x in group]),
        'mrr': mean([x['mrr'] for x in group]),
        'citation_precision': mean([x['citation_precision'] for x in group]),
        'citation_recall': mean([x['citation_recall'] for x in group]),
        'abstentions': sum(bool(x['abstained']) for x in group),
        'explicit_advice_refusals': refusals if category == 'advice' else None,
        'answerable_n': len(answerable),
    }
relevant = [x for x in rows if x['expected_source_ids']]
report = {
    'n': len(rows),
    'generation_mode': 'local extractive; external LLM disabled',
    'overall_evaluator_metrics': {
        'precision_at_5': mean([x['precision_at_k'] for x in rows]),
        'recall_at_5': mean([x['recall_at_k'] for x in rows]),
        'mrr_all_questions': mean([x['mrr'] for x in rows]),
        'citation_precision_all_questions': mean([x['citation_precision'] for x in rows]),
        'citation_recall_answerable_questions': mean([x['citation_recall'] for x in rows]),
    },
    'answerable_only': {
        'n': len(relevant),
        'mrr': mean([x['mrr'] for x in relevant]),
        'citation_precision': mean([x['citation_precision'] for x in relevant]),
        'citation_recall': mean([x['citation_recall'] for x in relevant]),
    },
    'out_of_corpus': {'n': len(groups['out_of_corpus']), 'abstentions': sum(bool(x['abstained']) for x in groups['out_of_corpus'])},
    'advice': {'n': len(groups['advice']), 'explicit_refusals': by_category['advice']['explicit_advice_refusals'], 'abstentions': by_category['advice']['abstentions']},
    'by_category': by_category,
}
(ROOT / 'data/evaluation/synthetic_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
selected_ids = {'q001', 'q021', 'q039', 'q119', 'q131', 'q155', 'q159', 'q174'}
selected = [x for x in rows if x['id'] in selected_ids]
(ROOT / 'data/evaluation/synthetic_cases.json').write_text(json.dumps(selected, indent=2, ensure_ascii=False), encoding='utf-8')
print('Saved data/evaluation/synthetic_report.json and synthetic_cases.json')
