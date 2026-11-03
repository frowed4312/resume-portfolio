"""Local HTTP contract tests; fixtures are not a semantic model evaluation."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import numpy as np
import pytest


@contextmanager
def embedding_server(reply):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, payload))
            status, response, headers = reply(payload, len(requests))
            body = json.dumps(response).encode()
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_embedding_batches_preserve_order_and_normalize_without_proxy(monkeypatch):
    from agent.embeddings import OllamaEmbeddings

    def reply(payload, _):
        return 200, {'embeddings': [[3, 4] if text == 'first' else [0, 2] for text in payload['input']]}, {}

    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
    monkeypatch.setenv('NO_PROXY', '')
    with embedding_server(reply) as (port, requests):
        encoder = OllamaEmbeddings('all-minilm', port)
        vectors = encoder.encode(['first'] + ['next'] * 32)
        assert vectors.shape == (33, 2)
        assert vectors.dtype == np.float32
        assert np.allclose(vectors[0], [.6, .8])
        assert np.allclose(vectors[1:], [0, 1])
        assert [len(body['input']) for _, body in requests] == [32, 1]
        assert all(path == '/api/embed' and body['truncate'] is False for path, body in requests)
        assert all(body['model'] == 'all-minilm' for _, body in requests)


@pytest.mark.parametrize('vectors', [[], [[1, 0], [1, 0]], [[0, 0]], [[1, float('nan')]],
                                    [[1, float('inf')]], [[]], [['bad', 1]], [[True, 1]]])
def test_malformed_vectors_are_rejected(vectors):
    from agent.embeddings import OllamaEmbeddings

    with embedding_server(lambda *_: (200, {'embeddings': vectors}, {})) as (port, _):
        with pytest.raises(ValueError, match='embedding'):
            OllamaEmbeddings('all-minilm', port).encode(['one'])


def test_vector_dimension_change_is_rejected_between_batches():
    from agent.embeddings import OllamaEmbeddings

    def reply(payload, call):
        return 200, {'embeddings': [[1] * (call + 1) for _ in payload['input']]}, {}

    with embedding_server(reply) as (port, _):
        with pytest.raises(ValueError, match='dimension'):
            OllamaEmbeddings('all-minilm', port).encode(['one'] * 33)


@pytest.mark.parametrize('status', [307, 404, 500])
def test_redirects_and_http_errors_are_not_followed_or_exposed(status):
    from agent.embeddings import OllamaEmbeddings

    with embedding_server(lambda *_: (status, {'error': 'private-document-text'},
                                     {'Location': 'http://127.0.0.1:1/secret'})) as (port, requests):
        with pytest.raises(RuntimeError) as error:
            OllamaEmbeddings('all-minilm', port).encode(['one'])
        assert 'private-document-text' not in str(error.value)
        assert 'secret' not in str(error.value)
        assert len(requests) == 1


def test_invalid_input_is_rejected_before_network_access():
    from agent.embeddings import OllamaEmbeddings

    encoder = OllamaEmbeddings('all-minilm', 1)
    for texts in [[], 'one', [None], [''], ['   '], ['x' * 1_000_001]]:
        with pytest.raises(ValueError):
            encoder.encode(texts)
    for model, port in [('', 1), ('bad model', 1), ('example-cloud', 1), ('all-minilm', 0), ('all-minilm', True)]:
        with pytest.raises(ValueError):
            OllamaEmbeddings(model, port)


def test_semantic_store_persists_and_rejects_mixed_indexes(tmp_path):
    from agent.embeddings import OllamaEmbeddings
    from agent.main import Store

    def reply(payload, _):
        return 200, {'embeddings': [[1, 0] if text in ('car', 'automobile') else [0, 1]
                                    for text in payload['input']]}, {}

    path = tmp_path / 'memory.db'
    with embedding_server(reply) as (port, _):
        with Store(path, embeddings=OllamaEmbeddings('all-minilm', port)) as store:
            store.ingest('vehicle.md', 'car')
            store.ingest('food.md', 'apple')
        with Store(path, embeddings=OllamaEmbeddings('all-minilm', port)) as store:
            assert store.search('automobile')[0]['source'] == 'vehicle.md'
        with pytest.raises(ValueError, match='index'):
            Store(path)
        with pytest.raises(ValueError, match='index'):
            Store(path, embeddings=OllamaEmbeddings('another-model', port))
