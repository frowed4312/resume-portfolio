"""Compare scan backends against temporary loopback listeners."""
import argparse
from contextlib import ExitStack
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import selectors
import socket
import statistics
import subprocess
import threading
from time import perf_counter

from security.main import scan


def run(native, output, rounds=10, nmap_dir=None):
    native = Path(native).resolve()
    if not native.is_file() or not 2 <= rounds <= 100:
        raise ValueError('Supply a built native worker and 2..100 rounds')
    samples = {'tcp': [], 'c': []}
    stop = threading.Event()
    with ExitStack() as stack:
        selector = stack.enter_context(selectors.DefaultSelector())
        ports = []
        for i in range(8):
            listener = stack.enter_context(socket.socket())
            listener.bind(('127.0.0.1', 0))
            ports.append(listener.getsockname()[1])
            if i < 4:
                listener.listen(128)
                listener.setblocking(False)
                selector.register(listener, selectors.EVENT_READ)
            # The other sockets reserve closed TCP ports for the entire run.

        def accept():
            while not stop.is_set():
                for key, _ in selector.select(.05):
                    try:
                        connection, _ = key.fileobj.accept()
                        connection.close()
                    except BlockingIOError:
                        pass

        thread = threading.Thread(target=accept, daemon=True)
        thread.start()
        targets = ['127.0.0.1', 'localhost']
        expected = {(target, '127.0.0.1', port) for target in targets for port in ports[:4]}
        try:
            for batch in range(rounds + 1):
                for mode in (['tcp', 'c'] if batch % 2 == 0 else ['c', 'tcp']):
                    start = perf_counter()
                    rows = scan(targets, targets, ports, mode=mode, workers=2, timeout=.1, native=native)
                    duration = (perf_counter() - start) * 1000
                    found = {(row['target'], item['ip'], item['port']) for row in rows for item in row['ports']}
                    if any(row['status'] != 'ok' for row in rows) or found != expected:
                        raise RuntimeError('Scan backends disagree with the listening sockets')
                    if batch:
                        samples[mode].append(duration)
        finally:
            stop.set(); thread.join()

    report = {'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                               'native_sha256': hashlib.sha256(native.read_bytes()).hexdigest()},
              'workload': {'targets': targets, 'ports': ports, 'open_ports': ports[:4], 'workers': 2,
                           'timeout_seconds': .1, 'rounds': rounds, 'warmup_rounds': 1,
                           'order': 'alternating backend order; end-to-end including DNS, subprocess startup and parsing'},
              'samples_ms': samples,
              'median_ms': {mode: statistics.median(values) for mode, values in samples.items()},
              'correctness': 'both backends matched all expected listening ports in every round',
              'limitations': ['loopback only', 'CPU frequency and background load uncontrolled',
                              'no significance test', 'Rust worker not exercised', 'live OSINT APIs not exercised']}
    if nmap_dir:
        old_path = os.environ.get('PATH', '')
        os.environ['PATH'] = str(Path(nmap_dir).resolve()) + os.pathsep + old_path
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
                self.wfile.write(b'<title>Local Nmap Lab</title>')
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            report['nmap_version'] = subprocess.run(['nmap', '--version'], text=True, capture_output=True, check=True).stdout
            report['nmap'] = scan(['127.0.0.1'], ['127.0.0.1'], [server.server_port], mode='nmap')
            if not report['nmap'][0]['ports'] or report['nmap'][0]['ports'][0]['service'].get('name') != 'http':
                raise RuntimeError('Nmap did not identify the local HTTP service')
        finally:
            server.shutdown(); server.server_close(); thread.join()
            os.environ['PATH'] = old_path
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    (output/'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=10)
    parser.add_argument('--nmap-dir', type=Path)
    parser.add_argument('--output', type=Path, default=Path('reports/security-integration'))
    args = parser.parse_args()
    print(json.dumps(run(args.native, args.output, args.rounds, args.nmap_dir), indent=2))
