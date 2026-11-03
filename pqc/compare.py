"""Compare Python wrapper and native C harness using the same liboqs DLL."""
import argparse
import csv
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
from pqc.main import MESSAGE, post_quantum

ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS = [('ML-KEM-512', True), ('ML-DSA-44', False), ('SLH_DSA_PURE_SHA2_128F', False)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', choices=[a for a, _ in ALGORITHMS])
    parser.add_argument('--iterations', type=int, default=200)
    parser.add_argument('--rounds', type=int, default=5)
    parser.add_argument('--warmup', type=int, default=20)
    parser.add_argument('--output', type=Path, default=Path('reports/pqc-comparison'))
    args = parser.parse_args()
    if not (1 <= args.iterations <= 10000 and 1 <= args.rounds <= 20 and 0 <= args.warmup <= 1000):
        parser.error('iterations=1..10000, rounds=1..20, warmup=0..1000')
    os.environ['OQS_INSTALL_PATH'] = str(ROOT / 'runtime/liboqs')
    if args.worker:
        with redirect_stdout(sys.stderr):
            import oqs
        result = post_quantum(oqs, args.worker, args.worker == 'ML-KEM-512', args.iterations, args.warmup)
        print(json.dumps(result))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    raw, summary = [], []
    binary = ROOT / 'runtime/liboqs/bin/oqs_bench.exe'
    for algorithm, kem in ALGORITHMS:
        operations = ['keygen', 'encapsulate', 'decapsulate'] if kem else ['keygen', 'sign', 'verify']
        for batch in range(args.rounds):
            # Alternate which process runs first to reduce order effects.
            for language in (['python', 'c'] if batch % 2 == 0 else ['c', 'python']):
                if language == 'python':
                    command = [sys.executable, '-m', 'pqc.compare', '--worker', algorithm,
                               '--iterations', str(args.iterations), '--warmup', str(args.warmup)]
                    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True, timeout=600)
                    result = json.loads(proc.stdout)
                    scores = {op: np.array(result['operations'][op]['raw_ns']) / 1000 for op in operations}
                else:
                    command = [str(binary), 'kem' if kem else 'sig', algorithm, str(args.iterations), str(args.warmup)]
                    proc = subprocess.run(command, text=True, capture_output=True, check=True, timeout=600)
                    rows = list(csv.DictReader(io.StringIO(proc.stdout)))
                    if len(rows) != args.iterations or any(int(r['message_bytes']) != len(MESSAGE) for r in rows):
                        raise RuntimeError('Native sample count/message length mismatch; rebuild C harness')
                    columns = ['keygen_us', 'encapsulate_or_sign_us', 'decapsulate_or_verify_us']
                    scores = {op: np.array([float(r[col]) for r in rows]) for op, col in zip(operations, columns)}
                for op, samples in scores.items():
                    raw.append({'algorithm': algorithm, 'round': batch, 'language': language,
                                'operation': op, 'samples_us': samples.tolist(), 'median_us': float(np.median(samples))})
            print(f'{algorithm}: round {batch + 1}/{args.rounds}', flush=True)
        for op in operations:
            py = [r['median_us'] for r in raw if r['algorithm'] == algorithm and r['operation'] == op and r['language'] == 'python']
            c = [r['median_us'] for r in raw if r['algorithm'] == algorithm and r['operation'] == op and r['language'] == 'c']
            py_median, c_median = float(np.median(py)), float(np.median(c))
            ratios = np.array(py) / np.array(c)
            summary.append({'algorithm': algorithm, 'operation': op, 'python_us': py_median, 'c_us': c_median,
                            'speedup': py_median / c_median, 'time_saved_percent': 100 * (1 - c_median / py_median),
                            'round_speedup_min': float(ratios.min()), 'round_speedup_max': float(ratios.max())})
    metadata = {'platform': platform.platform(), 'python': platform.python_version(), 'message_bytes': len(MESSAGE),
                'message_sha256': hashlib.sha256(MESSAGE).hexdigest(),
                'dll_sha256': hashlib.sha256((binary.parent / 'liboqs.dll').read_bytes()).hexdigest(),
                'iterations_per_round': args.iterations, 'rounds': args.rounds, 'warmup_per_round': args.warmup,
                'order': 'sequential alternating Python/C; fresh process for each batch'}
    (args.output / 'results.json').write_text(json.dumps({'metadata': metadata, 'summary': summary, 'raw': raw}, indent=2))
    lines = ['# Python wrapper vs C: liboqs benchmark', '',
             f'Windows x64; same DLL; message {len(MESSAGE)} bytes; {args.rounds} rounds x {args.iterations} samples per operation/language; {args.warmup} warmups per batch.', '',
             'Reported latency is the median of batch medians. Speedup = Python / C (greater than 1 favors C).', '',
             '| Algorithm | Operation | Python µs | C µs | Speedup | Time saved |',
             '|---|---|---:|---:|---:|---:|']
    for row in summary:
        lines.append(f'| {row["algorithm"]} | {row["operation"]} | {row["python_us"]:.2f} | {row["c_us"]:.2f} | {row["speedup"]:.2f}x | {row["time_saved_percent"]:.1f}% |')
    lines += ['', '## Interpretation and limits', '',
              'Both paths execute the same C cryptographic implementation. This measures Python-wrapper versus direct-C harness overhead, not Python versus C implementations of the algorithms.',
              'C reuses buffers; the Python wrapper allocates/copies Python/ctypes buffers. Those costs are included. Library object setup, process startup, output serialization, and post-operation correctness checks are outside the measured regions.',
              'Keys and signing randomness are fresh, not identical. Order alternates, but CPU frequency, scheduling and background load remain uncontrolled. Batch speedup ranges and all raw samples are in results.json. No claim of statistical significance or whole-application speedup.',
              'C performs successful signature verification and KEM agreement checks. Python additionally checks rejection of a modified message outside the timed region.',
              'Historical native CSVs in reports/pqc used the previous 16-byte message. Use this new comparison for matched workloads.']
    (args.output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
