"""Wall-clock timings with verification outside timed regions."""
import argparse
import csv
import ctypes.util
import importlib.util
import json
import os
import platform
from pathlib import Path
from time import perf_counter_ns

import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

MESSAGE = b'resume portfolio cryptography benchmark' * 8


def summarize(samples):
    values = np.asarray(samples, dtype=float) / 1000
    return {'samples': len(samples), 'median_us': float(np.median(values)),
            'mean_us': float(values.mean()), 'p95_us': float(np.quantile(values, .95)),
            'raw_ns': samples}


def timed(fn):
    start = perf_counter_ns()
    result = fn()
    return result, perf_counter_ns() - start


def classical(kind, iterations):
    timings = {key: [] for key in ('keygen', 'sign', 'verify')} if kind != 'ECDH-P256' else {key: [] for key in ('keygen', 'exchange')}
    for iteration in range(iterations + 1):
        private, duration = timed(lambda: rsa.generate_private_key(65537, 3072) if kind == 'RSA-PSS-3072' else ec.generate_private_key(ec.SECP256R1()))
        public = private.public_key()
        values = {'keygen': duration}
        if kind == 'ECDH-P256':
            peer = ec.generate_private_key(ec.SECP256R1())
            shared, values['exchange'] = timed(lambda: private.exchange(ec.ECDH(), peer.public_key()))
            if shared != peer.exchange(ec.ECDH(), public):
                raise RuntimeError('ECDH agreement failed')
            signature = None
        else:
            arguments = (padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256()) if kind == 'RSA-PSS-3072' else (ec.ECDSA(hashes.SHA256()),)
            signature, values['sign'] = timed(lambda: private.sign(MESSAGE, *arguments))
            _, values['verify'] = timed(lambda: public.verify(signature, MESSAGE, *arguments))
            try:
                public.verify(signature, MESSAGE + b'x', *arguments)
            except InvalidSignature:
                pass
            else:
                raise RuntimeError('Tampered message accepted')
        if iteration:  # First iteration is warmup.
            for key in timings:
                timings[key].append(values[key])
    return {'algorithm': kind, 'classical_security_bits': 128, 'nist_pqc_category': None,
            'verified': True, 'key_encoding': 'DER SPKI / PKCS8 (unencrypted; size only)',
            'public_key_bytes': len(public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)),
            'private_key_bytes': len(private.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())),
            'signature_bytes': len(signature) if signature else None,
            'operations': {k: summarize(v) for k, v in timings.items()}}


def post_quantum(oqs, algorithm, kem, iterations, warmup=1):
    operations = ('keygen', 'encapsulate', 'decapsulate') if kem else ('keygen', 'sign', 'verify')
    timings = {key: [] for key in operations}
    cls = oqs.KeyEncapsulation if kem else oqs.Signature
    for iteration in range(iterations + warmup):
        with cls(algorithm) as engine:
            public, keygen = timed(engine.generate_keypair)
            private_size = len(engine.export_secret_key())
            if kem:
                with cls(algorithm) as sender:
                    (ciphertext, shared), encapsulate = timed(lambda: sender.encap_secret(public))
                recovered, decapsulate = timed(lambda: engine.decap_secret(ciphertext))
                if recovered != shared:
                    raise RuntimeError('KEM shared secrets disagree')
                values = (keygen, encapsulate, decapsulate)
                payload_size = len(ciphertext)
            else:
                signature, sign = timed(lambda: engine.sign(MESSAGE))
                ok, verify = timed(lambda: engine.verify(MESSAGE, signature, public))
                if not ok or engine.verify(MESSAGE + b'x', signature, public):
                    raise RuntimeError('Signature verification invariant failed')
                values = (keygen, sign, verify)
                payload_size = len(signature)
            if iteration >= warmup:
                for key, value in zip(operations, values):
                    timings[key].append(value)
            category = engine.details['claimed_nist_level']
    return {'algorithm': algorithm, 'verified': True, 'classical_security_bits': None,
            'nist_pqc_category': category, 'key_encoding': 'raw liboqs',
            'public_key_bytes': len(public), 'private_key_bytes': private_size,
            'ciphertext_bytes' if kem else 'signature_bytes': payload_size,
            'operations': {k: summarize(v) for k, v in timings.items()}}


def benchmark(iterations=10, include_pqc=True):
    if not 1 <= iterations <= 10000:
        raise ValueError('iterations must be between 1 and 10000')
    result = {'environment': {'platform': platform.platform(), 'python': platform.python_version(),
               'openssl': backend.openssl_version_text(), 'message_bytes': len(MESSAGE), 'warmup': 1},
              'results': [classical(name, iterations) for name in ('RSA-PSS-3072', 'ECDSA-P256', 'ECDH-P256')],
              'unavailable': []}
    if include_pqc:
        # Do not import an absent wrapper: some wrappers auto-download/build native libraries.
        bundled = Path(__file__).resolve().parents[1] / 'runtime' / 'liboqs'
        default_install = bundled if os.name == 'nt' and (bundled / 'bin' / 'liboqs.dll').is_file() else Path.home() / '_oqs'
        install = Path(os.environ.get('OQS_INSTALL_PATH', str(default_install)))
        libraries = [install / subdir / filename for subdir in ('bin', 'lib', 'lib64')
                     for filename in ('oqs.dll', 'liboqs.dll', 'liboqs.so', 'liboqs.dylib')]
        if importlib.util.find_spec('oqs') is None or not (any(p.is_file() for p in libraries) or ctypes.util.find_library('oqs')):
            result['unavailable'].append('liboqs native library or liboqs-python absent; see pqc/README.md. No auto-install attempted.')
        else:
            os.environ.setdefault('OQS_INSTALL_PATH', str(install))
            import oqs
            result['environment']['liboqs'] = oqs.oqs_version()
            for algorithm, kem in [('ML-KEM-512', True), ('ML-DSA-44', False), ('SLH_DSA_PURE_SHA2_128F', False)]:
                enabled = oqs.get_enabled_kem_mechanisms() if kem else oqs.get_enabled_sig_mechanisms()
                if algorithm not in enabled:
                    result['unavailable'].append(algorithm)
                    continue
                result['results'].append(post_quantum(oqs, algorithm, kem, iterations))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations', type=int, default=10)
    parser.add_argument('--classical-only', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('reports/pqc'))
    args = parser.parse_args()
    report = benchmark(args.iterations, not args.classical_only)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'benchmark.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (args.output / 'latencies.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['algorithm', 'operation', 'samples', 'median_us', 'p95_us'])
        for row in report['results']:
            for operation, stats in row['operations'].items():
                writer.writerow([row['algorithm'], operation, stats['samples'], stats['median_us'], stats['p95_us']])
    print(json.dumps(report, indent=2))
