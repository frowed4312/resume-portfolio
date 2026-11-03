"""Neural embeddings from an explicitly installed local Ollama model."""
import json
import re
import urllib.error
import urllib.request

import numpy as np


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaEmbeddings:
    """Encode text locally. An optional digest labels the stored index identity.

    Construction is offline; a supplied digest is not verified against the server.
    Changing the model behind a tag
    requires a fresh database or reindex, even when its vector dimension is unchanged.
    Run Ollama with OLLAMA_NO_CLOUD=1 to disable server-side cloud forwarding.
    """

    def __init__(self, model: str, port: int = 11434, model_digest: str | None = None):
        if (not isinstance(model, str) or len(model) > 200
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]*', model)
                or model.lower().endswith('cloud')):
            raise ValueError('Supply an installed local embedding model name')
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Supply a valid localhost port')
        if model_digest is not None and (not isinstance(model_digest, str)
                                        or not re.fullmatch(r'[a-fA-F0-9]{64}', model_digest)):
            raise ValueError('Model digest must be a 64-character SHA-256 hex string')
        self.model = model
        self.port = port
        self.identity = 'ollama-embed-v1:' + model
        if model_digest is not None:
            self.identity += '@sha256:' + model_digest.lower()
        self._dimension = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if (not isinstance(texts, list) or not 1 <= len(texts) <= 4096
                or any(not isinstance(s, str) or not s.strip() or len(s) > 1_000_000 for s in texts)):
            raise ValueError('Supply 1..4096 nonempty texts, each at most 1000000 characters')
        if sum(map(len, texts)) > 4_000_000:
            raise ValueError('Embedding input exceeds 4000000 characters')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        batches = []
        dimension = self._dimension
        for start in range(0, len(texts), 32):
            batch = texts[start:start + 32]
            payload = {'model': self.model, 'input': batch, 'truncate': False}
            request = urllib.request.Request(f'http://127.0.0.1:{self.port}/api/embed',
                                             data=json.dumps(payload).encode('utf-8'),
                                             headers={'Content-Type': 'application/json'})
            try:
                with opener.open(request, timeout=120) as response:
                    body = response.read(8_000_001)
            except OSError:
                raise RuntimeError('Local embedding request failed; check the server and installed model') from None
            if len(body) > 8_000_000:
                raise ValueError('Local embedding response exceeds the size limit')
            try:
                parsed = json.loads(body)
            except (ValueError, UnicodeError):
                raise ValueError('Invalid local embedding JSON response') from None
            vectors = parsed.get('embeddings') if isinstance(parsed, dict) else None
            if (not isinstance(vectors, list) or len(vectors) != len(batch)
                    or any(not isinstance(row, list) or not 1 <= len(row) <= 8192
                           or any(type(v) not in (int, float) for v in row) for row in vectors)):
                raise ValueError('Invalid local embedding vectors')
            current_dimension = len(vectors[0])
            if any(len(row) != current_dimension for row in vectors):
                raise ValueError('Inconsistent embedding dimension')
            if dimension is not None and dimension != current_dimension:
                raise ValueError('Local embedding dimension changed; rebuild the index with a fixed model')
            dimension = current_dimension
            try:
                matrix = np.asarray(vectors, dtype=np.float64)
            except (ValueError, OverflowError):
                raise ValueError('Invalid local embedding numeric values') from None
            if not np.isfinite(matrix).all():
                raise ValueError('Local embedding vectors must be finite')
            # Rescale before taking norms to avoid overflow with unusually large values.
            scale = np.max(np.abs(matrix), axis=1, keepdims=True)
            if np.any(scale == 0):
                raise ValueError('Local embedding vectors must be nonzero')
            matrix /= scale
            matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
            batches.append(matrix.astype(np.float32))
        self._dimension = dimension
        return np.vstack(batches)
