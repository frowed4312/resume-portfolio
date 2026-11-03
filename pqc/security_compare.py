"""Compare measured operations with explicit classical and PQC security references."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from pqc.main import benchmark


REFERENCES = {
    'classical': 'https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-57pt1r5.pdf',
    'categories': 'https://csrc.nist.gov/Projects/Post-Quantum-Cryptography/Post-Quantum-Cryptography-Standardization/Evaluation-Criteria/Security-(Evaluation-Criteria)',
    'faq': 'https://csrc.nist.gov/projects/post-quantum-cryptography/faqs',
}
PROFILES = {
    'RSA-PSS-3072': ('signature', None, 'RSA-3072 classical estimate', False),
    'ECDSA-P256': ('signature', None, 'P-256 classical estimate', False),
    'ECDH-P256': ('key agreement', None, 'P-256 classical estimate', False),
    'ML-KEM-512': ('KEM', 1, 'AES-128 key search', True),
    'ML-DSA-44': ('signature', 2, 'SHA-256 collision search', True),
    'SLH_DSA_PURE_SHA2_128F': ('signature', 1, 'AES-128 key search', True),
}


def build_comparison(measurements):
    profiles, rows = [], {}
    for row in measurements['results']:
        name = row['algorithm']
        if name not in PROFILES:
            raise ValueError('No security profile for ' + name)
        if name in rows or not row.get('verified'):
            raise ValueError('Expected unique, verified measurements')
        family, category, reference, quantum = PROFILES[name]
        if row.get('nist_pqc_category') != category:
            raise ValueError('Unexpected NIST category for ' + name)
        if category is None and row.get('classical_security_bits') != 128:
            raise ValueError('Expected 128-bit classical baseline for ' + name)
        profiles.append({'algorithm': name, 'family': family, 'nist_pqc_category': category,
                         'reference_problem': reference, 'quantum_resistant': quantum,
                         'classical_reference_bits': 128,
                         'reference_note': 'Coarse classical reference grouping, not an exact attack-cost estimate or equal quantum security.'})
        rows[name] = row
    pairs = []
    for classical in ('RSA-PSS-3072', 'ECDSA-P256'):
        for pqc in ('ML-DSA-44', 'SLH_DSA_PURE_SHA2_128F'):
            if classical not in rows or pqc not in rows:
                continue
            ratios = {}
            for operation in ('keygen', 'sign', 'verify'):
                a = rows[classical]['operations'][operation]['median_us']
                b = rows[pqc]['operations'][operation]['median_us']
                if a <= 0 or b <= 0:
                    raise ValueError('Latency must be positive')
                ratios[operation] = {'classical_us': a, 'pqc_us': b, 'pqc_over_classical': b / a}
            pairs.append({'classical': classical, 'pqc': pqc,
                          'comparison_basis': '128-bit classical reference tier; distinct PQC categories retained',
                          'equivalent_quantum_security': False, 'operations': ratios})
    return {'status': 'complete' if set(rows) == set(PROFILES) and not measurements.get('unavailable') else 'partial',
            'profiles': profiles, 'pairs': pairs,
            'key_establishment': [rows[n] for n in ('ECDH-P256', 'ML-KEM-512') if n in rows],
            'unavailable': measurements.get('unavailable', []), 'references': REFERENCES,
            'limitations': [
                'RSA and ECC are not quantum resistant. No parameter size gives them PQC-equivalent quantum security.',
                'Categories 1 and 2 have different reference problems; a shared classical reference tier does not make them the same category.',
                'ECDH exchange and KEM encapsulation/decapsulation have different roles and security definitions; no cross-operation speedup is calculated.',
                'Classical keys use DER and PQC keys use raw encoding. Serialized sizes include different overheads.',
                'Single-machine timings include Python/FFI overhead and are not a statistical performance study.',
            ]}


def write_report(output, measurements, comparison):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'measurements.json').write_text(json.dumps(measurements, indent=2), encoding='utf-8')
    (output / 'comparison.json').write_text(json.dumps(comparison, indent=2), encoding='utf-8')
    lines = ['# Cryptography comparison by security reference', '',
             f"Status: {comparison['status']}. Measured at {measurements['measured_at_utc']}.", '',
             'The algorithms below share a coarse 128-bit classical reference tier. Their quantum security differs. NIST categories describe reference attack problems, not interchangeable bit counts.', '',
             '| Algorithm | Role | PQC category | Reference | Quantum resistant |',
             '|---|---|---:|---|---|']
    for p in comparison['profiles']:
        lines.append(f"| {p['algorithm']} | {p['family']} | {p['nist_pqc_category'] or 'N/A'} | {p['reference_problem']} | {'Yes' if p['quantum_resistant'] else 'No'} |")
    lines += ['', '## Operation timings', '',
              'Medians in microseconds. Every row includes a correctness check outside the timed region. Raw samples are in measurements.json.', '',
              '| Algorithm | Operation | Samples | Median us | p95 us |', '|---|---|---:|---:|---:|']
    for row in measurements['results']:
        for op, stats in row['operations'].items():
            lines.append(f"| {row['algorithm']} | {op} | {stats['samples']} | {stats['median_us']:.2f} | {stats['p95_us']:.2f} |")
    lines += ['', '## Serialized sizes', '', '| Algorithm | Public key | Private key | Signature | Ciphertext | Encoding |', '|---|---:|---:|---:|---:|---|']
    for row in measurements['results']:
        lines.append(f"| {row['algorithm']} | {row['public_key_bytes']} | {row['private_key_bytes']} | {row.get('signature_bytes') or '-'} | {row.get('ciphertext_bytes') or '-'} | {row['key_encoding']} |")
    lines += ['', '## Signature comparisons', '',
              'Ratios are PQC median / classical median. Values below one favor PQC. Only matching signature operations are paired.', '',
              '| Classical | PQC | Keygen ratio | Sign ratio | Verify ratio |', '|---|---|---:|---:|---:|']
    for p in comparison['pairs']:
        ratios = ' | '.join(f"{p['operations'][op]['pqc_over_classical']:.3f}" for op in ('keygen', 'sign', 'verify'))
        lines.append(f"| {p['classical']} | {p['pqc']} | {ratios} |")
    lines += ['', '## Limits', '', *['- ' + s for s in comparison['limitations']], '', '## Sources', '']
    lines.extend(f'- [{name}]({url})' for name, url in REFERENCES.items())
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations', type=int, default=30)
    parser.add_argument('--output', type=Path, default=Path('reports/security-levels'))
    args = parser.parse_args()
    measurements = benchmark(args.iterations)
    measurements['measured_at_utc'] = datetime.now(timezone.utc).isoformat()
    comparison = build_comparison(measurements)
    write_report(args.output, measurements, comparison)
    print(json.dumps({'status': comparison['status'], 'algorithms': len(comparison['profiles']),
                      'signature_pairs': len(comparison['pairs']), 'output': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
