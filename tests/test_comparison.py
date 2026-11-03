import csv
import io
from pathlib import Path
import subprocess
from pqc.main import MESSAGE


def test_native_comparison_message_and_sample_count():
    executable = Path(__file__).resolve().parents[1] / 'runtime/liboqs/bin/oqs_bench.exe'
    result = subprocess.run([str(executable), 'sig', 'ML-DSA-44', '3', '2'], capture_output=True, text=True, check=True)
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert len(rows) == 3
    assert all(int(row['message_bytes']) == len(MESSAGE) for row in rows)
