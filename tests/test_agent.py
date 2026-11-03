import json
import pytest
from agent.main import Store, execute_tool, run, validate_plan


def test_retrieval_persists_and_replaces(tmp_path):
    db = tmp_path / 'memory.sqlite3'
    with Store(db) as store:
        store.ingest('quantum.md', 'Shor quantum algorithm uses period finding to factor integers.')
        store.ingest('sensor.md', 'Sensor anomaly detection uses isolation forests and reconstruction error.')
        assert store.search('quantum period')[0]['source'] == 'quantum.md'
        store.ingest('quantum.md', 'Replacement text')
    with Store(db) as store:
        assert len(store.search('sensor anomaly')) == 1
        assert store.search('quantum period') == []


def test_local_workflow_and_memory(tmp_path):
    with Store(tmp_path / 'state.sqlite3') as store:
        store.ingest('guide.md', 'Precision counts correct alerts. Recall counts detected anomalies.')
        result = run('Explain anomaly recall', store, tmp_path / 'reports', mode='demo')
        assert result['status'] == 'completed'
        assert 'guide.md' in result['answer']
        assert len(store.history('default')) == 2
        assert list((tmp_path / 'reports').glob('*.md'))


def test_tool_boundary_and_invalid_plan(tmp_path):
    with Store(tmp_path / 'db.sqlite3') as store:
        with pytest.raises(ValueError):
            execute_tool('write_report', {'filename': '../escape.md', 'text': 'bad'}, store, tmp_path)
        with pytest.raises(ValueError):
            execute_tool('shell', {'command': 'whoami'}, store, tmp_path)
        with pytest.raises(ValueError):
            validate_plan({'steps': ['one'] * 9})


def test_empty_corpus_is_explicit(tmp_path):
    with Store(tmp_path / 'db.sqlite3') as store:
        result = run('unknown', store, tmp_path / 'reports', mode='demo')
        assert 'No matching' in result['answer']
def test_report_requires_retrieved_source_before_writing():
    from agent.main import validate_report_evidence
    import pytest
    with pytest.raises(ValueError, match='Search'):
        validate_report_evidence('Recall [guide.md]', [])
    trace = [{'tool': 'search_notes', 'result': [{'source': 'guide.md', 'text': 'Recall'}]}]
    with pytest.raises(ValueError, match='source'):
        validate_report_evidence('Recall is useful.', trace)
    validate_report_evidence('Recall is useful [guide.md].', trace)

