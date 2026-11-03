import pytest

from pqc.security_compare import build_comparison


def row(name, category=None, bits=None, operations=('keygen', 'sign', 'verify')):
    return {'algorithm': name, 'nist_pqc_category': category,
            'classical_security_bits': bits, 'verified': True,
            'operations': {op: {'median_us': 2, 'samples': 4} for op in operations}}


def test_categories_are_kept_separate_from_classical_baseline():
    report = build_comparison({'results': [row('RSA-PSS-3072', bits=128),
        row('ML-DSA-44', category=2), row('SLH_DSA_PURE_SHA2_128F', category=1)], 'unavailable': []})
    profiles = {r['algorithm']: r for r in report['profiles']}
    assert profiles['ML-DSA-44']['nist_pqc_category'] == 2
    assert profiles['ML-DSA-44']['reference_problem'] == 'SHA-256 collision search'
    assert profiles['RSA-PSS-3072']['quantum_resistant'] is False
    assert all(not pair['equivalent_quantum_security'] for pair in report['pairs'])
    assert len(report['pairs']) == 2


def test_no_ecdh_to_kem_latency_ratio():
    report = build_comparison({'results': [row('ECDH-P256', bits=128, operations=('keygen', 'exchange')),
        row('ML-KEM-512', category=1, operations=('keygen', 'encapsulate', 'decapsulate'))], 'unavailable': []})
    assert report['pairs'] == []
    assert len(report['key_establishment']) == 2


def test_wrong_category_and_unverified_results_are_rejected():
    with pytest.raises(ValueError, match='category'):
        build_comparison({'results': [row('ML-DSA-44', category=1)]})
    r = row('RSA-PSS-3072', bits=128)
    r['verified'] = False
    with pytest.raises(ValueError, match='verified'):
        build_comparison({'results': [r]})


def test_incomplete_measurement_is_not_a_complete_comparison():
    report = build_comparison({'results': [row('RSA-PSS-3072', bits=128)], 'unavailable': ['liboqs']})
    assert report['status'] == 'partial'
    assert report['unavailable'] == ['liboqs']
