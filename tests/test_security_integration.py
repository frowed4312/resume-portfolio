import datetime
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from security.main import scan, web_metadata, enrich
import security.main as inventory


@pytest.fixture
def https_lab(tmp_path):
    key = rsa.generate_private_key(65537, 2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path/'cert.pem', tmp_path/'key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'<title>Local Inventory Lab</title><meta name="description" content="TLS integration test">')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_port, ssl.create_default_context(cafile=str(cert_path))
    server.shutdown(); server.server_close(); thread.join()


def test_https_fetch_uses_verified_local_tls(https_lab):
    port, context = https_lab
    result = web_metadata('127.0.0.1', port=port, ssl_context=context)
    assert result == {'status': 'ok', 'title': 'Local Inventory Lab', 'description': 'TLS integration test'}
    assert web_metadata('127.0.0.1', port=port)['status'] == 'error'


@pytest.mark.skipif(not os.environ.get('SECURITY_NATIVE'), reason='Set SECURITY_NATIVE to a compiled C worker')
def test_c_worker_matches_python_and_rejects_invalid_input():
    executable = os.environ['SECURITY_NATIVE']
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0)); server.listen(64)
        port = server.getsockname()[1]
        for mode in ['tcp', 'c']:
            rows = scan(['127.0.0.1', 'localhost'], ['127.0.0.1', 'localhost'], [port], mode=mode, native=executable)
            assert all(r['status'] == 'ok' for r in rows)
            assert all(any(p['port'] == port and p['ip'] == '127.0.0.1' for p in r['ports']) for r in rows)
        for ports in ['0', '65536', '80,', ',80', '80,,81', '80x']:
            result = subprocess.run([executable, '127.0.0.1', ports, '100'], capture_output=True, timeout=5)
            assert result.returncode == 2
            assert result.stdout == b''


def test_provider_routes_and_missing_credentials(monkeypatch):
    monkeypatch.delenv('SHODAN_API_KEY', raising=False)
    monkeypatch.delenv('VIRUSTOTAL_API_KEY', raising=False)
    row = {'target': 'example.org', 'resolved_ips': ['192.0.2.1']}
    missing = enrich(row, ['shodan', 'virustotal'])['osint']
    assert all(value['status'] == 'unavailable' for value in missing.values())
    requests = []
    def fixture_fetch(url, headers=None):
        requests.append((url, headers))
        return {'status': 'error', 'http_status': 429}
    monkeypatch.setenv('SHODAN_API_KEY', 'test-placeholder')
    monkeypatch.setenv('VIRUSTOTAL_API_KEY', 'test-placeholder')
    monkeypatch.setattr(inventory, 'fetch_json', fixture_fetch)
    result = enrich(row, ['shodan', 'virustotal'])['osint']
    assert requests[0][0].endswith('/domains/example.org')
    assert requests[0][1] == {'x-apikey': 'test-placeholder'}
    assert '/shodan/host/192.0.2.1?' in requests[1][0]
    assert result['virustotal']['http_status'] == 429
    assert result['shodan']['192.0.2.1']['http_status'] == 429
    assert 'test-placeholder' not in json.dumps(result)
