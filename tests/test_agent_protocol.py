"""Exercise the planner and worker HTTP flow with a local test server."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
import pytest
from agent.main import Store, run


def test_ollama_planner_worker_tool_roundtrip(tmp_path):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            if body.get('format'):
                assert body['format']['properties']['steps']['items']['type'] == 'string'
                content = {'role': 'assistant', 'content': json.dumps({'steps': ['Find evidence', 'Answer']})}
            elif body['messages'][-1]['role'] == 'tool':
                assert 'guide.md' in body['messages'][-1]['content']
                content = {'role': 'assistant', 'content': 'Recall counts detected anomalies [guide.md].'}
            else:
                content = {'role': 'assistant', 'content': '', 'tool_calls': [
                    {'function': {'name': 'search_notes', 'arguments': {'query': 'recall'}}}]}
            payload = json.dumps({'message': content}).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(payload))); self.end_headers()
            self.wfile.write(payload)

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with Store(tmp_path / 'state.sqlite3') as store:
            store.ingest('guide.md', 'Recall counts detected anomalies.')
            result = run('Explain recall', store, tmp_path, mode='ollama', model='protocol-fixture', port=server.server_port)
            assert result['status'] == 'completed'
            assert result['trace'][0]['tool'] == 'search_notes'
            assert len(requests) == 3
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_failed_run_is_persisted(tmp_path):
    with Store(tmp_path / 'state.sqlite3') as store:
        with pytest.raises(ValueError):
            run('test', store, tmp_path, mode='ollama', model=None)
        state = json.loads(store.db.execute('SELECT state FROM runs').fetchone()[0])
        assert state['status'] == 'failed'
