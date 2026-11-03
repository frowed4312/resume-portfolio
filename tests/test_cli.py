import json
from pathlib import Path
import subprocess
import sys


def test_quantum_cli_writes_circuit(tmp_path):
    result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'quantum.main', '--output', str(tmp_path)],
                            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1], timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / 'result.json').read_text())['factors'] == [3, 5]
    assert (tmp_path / 'circuit.txt').stat().st_size > 10
