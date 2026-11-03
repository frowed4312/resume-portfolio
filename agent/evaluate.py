"""Small real-model smoke evaluation, not a general agent benchmark."""
import argparse
import json
from pathlib import Path
import tempfile
import time

from agent.embeddings import OllamaEmbeddings
from agent.main import Store, run


def evaluate(model, port, embedding_model, directory, cpu=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cases = [
        ('explain', 'Explain precision and recall using the notes. Cite the source.'),
        ('report', 'Search the notes and save a report named metrics.md explaining precision and recall. Cite the source.'),
        ('followup', 'Which metric from our earlier discussion measures missed anomalies? Search the notes and cite the source.'),
    ]
    results = []
    # A fresh database avoids old notes or responses affecting the experiment.
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        path = Path(temporary)
        for name, task in cases:
            started = time.perf_counter()
            embeddings = OllamaEmbeddings(embedding_model, port) if embedding_model else None
            with Store(path / 'memory.db', embeddings=embeddings) as store:
                store.ingest('metrics.md', 'Precision is TP/(TP+FP), the fraction of alerts that are true anomalies. '
                             'Recall is TP/(TP+FN), the fraction of actual anomalies detected. Low recall means more missed anomalies.')
                try:
                    state = run(task, store, path / 'reports', mode='ollama', model=model,
                                port=port, session='evaluation', cpu=cpu)
                    searched = any(row['tool'] == 'search_notes' and isinstance(row['result'], list)
                                   and row['result'] for row in state['trace'])
                    answer = state['answer']
                    checks = {'retrieved_evidence': bool(searched), 'mentions_source': 'metrics.md' in answer,
                              'mentions_metric': 'recall' in answer.lower()}
                    if name == 'report':
                        report = path / 'reports' / 'metrics.md'
                        checks['report_saved'] = report.is_file()
                        checks['report_cites_source'] = report.is_file() and 'metrics.md' in report.read_text(encoding='utf-8')
                    results.append({'case': name, 'task': task, 'checks': checks,
                                    'passed': all(checks.values()), 'state': state})
                except Exception as exc:
                    results.append({'case': name, 'task': task, 'passed': False, 'error': str(exc)})
            results[-1]['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    evidence = {'model': model, 'embedding_model': embedding_model, 'cpu_generation': cpu,
                'scope': 'Three smoke tasks on one short English note. Automated checks do not prove factual correctness.',
                'results': results}
    (directory / 'local-evaluation.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--port', type=int, default=11434)
    parser.add_argument('--embedding-model')
    parser.add_argument('--cpu', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('reports/agent'))
    args = parser.parse_args()
    result = evaluate(args.model, args.port, args.embedding_model, args.output, cpu=args.cpu)
    print(json.dumps({'passed': sum(row['passed'] for row in result['results']), 'total': len(result['results'])}))
