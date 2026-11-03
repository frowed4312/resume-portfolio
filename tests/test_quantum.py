import numpy as np
import pytest
from qiskit.quantum_info import Operator
from quantum.main import inverse_qft, multiplication, factor


def test_inverse_qft_matches_dft():
    size = 8
    expected = np.exp(-2j * np.pi * np.outer(np.arange(size), np.arange(size)) / size) / np.sqrt(size)
    assert np.allclose(Operator(inverse_qft(3)).data, expected)


def test_modular_multiplication_is_unitary():
    matrix = multiplication(2, 15)
    assert np.allclose(matrix.T @ matrix, np.eye(16))
    assert np.argmax(matrix[:, 7]) == 14
    assert np.argmax(matrix[:, 15]) == 15


@pytest.mark.parametrize('number,base,expected', [(15, 2, [3, 5]), (21, 2, [3, 7])])
def test_real_order_finding(number, base, expected):
    result = factor(number, base, shots=256, seed=42)
    assert result['factors'] == expected
    assert result['counts']


@pytest.mark.parametrize('number,base', [(97, 2), (15, 15), (2, 2), (15, -1)])
def test_invalid_or_large_circuits(number, base):
    with pytest.raises(ValueError):
        factor(number, base)
