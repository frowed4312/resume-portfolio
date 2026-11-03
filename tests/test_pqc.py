import pytest
import os
from pqc.main import benchmark, summarize


def test_statistics_and_validation():
    stats = summarize([1000, 2000, 3000])
    assert stats['median_us'] == 2
    assert stats['samples'] == 3
    with pytest.raises(ValueError):
        benchmark(0)


def test_actual_classical_operations():
    result = benchmark(2, include_pqc=False)
    assert len(result['results']) == 3
    for row in result['results']:
        assert row['verified'] is True
        assert row['public_key_bytes'] > 0
        assert row['operations']['keygen']['median_us'] > 0


@pytest.mark.skipif(not os.environ.get('OQS_INSTALL_PATH'), reason='Native liboqs integration requires OQS_INSTALL_PATH')
def test_native_pqc_algorithms():
    result = benchmark(2)
    assert not result['unavailable']
    rows = {row['algorithm']: row for row in result['results']}
    assert rows['ML-KEM-512']['ciphertext_bytes'] == 768
    assert rows['ML-DSA-44']['signature_bytes'] == 2420
    assert rows['SLH_DSA_PURE_SHA2_128F']['signature_bytes'] == 17088
    assert all(row['verified'] for row in rows.values())
