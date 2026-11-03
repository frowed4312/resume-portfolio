"""Simulate small Shor factoring circuits with Qiskit."""
import argparse
from collections import Counter
from fractions import Fraction
import json
import math
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import UnitaryGate
from qiskit.quantum_info import Statevector


def inverse_qft(n):
    circuit = QuantumCircuit(n, name='inverse QFT')
    for j in range(n // 2):
        circuit.swap(j, n - 1 - j)
    for j in range(n):
        for m in range(j):
            circuit.cp(-math.pi / 2 ** (j - m), m, j)
        circuit.h(j)
    return circuit


def multiplication(a, number):
    if math.gcd(a, number) != 1:
        raise ValueError('Modular multiplication must be invertible.')
    size = 2 ** math.ceil(math.log2(number))
    matrix = np.zeros((size, size))
    for x in range(size):
        matrix[(a * x) % number if x < number else x, x] = 1
    return matrix


def order_circuit(number, base):
    work = math.ceil(math.log2(number))
    precision = 2 * work
    circuit = QuantumCircuit(precision + work)
    circuit.h(range(precision))
    circuit.x(precision)  # Work register starts at |1>.
    for j in range(precision):
        matrix = multiplication(pow(base, 2 ** j, number), number)
        gate = UnitaryGate(matrix, label=f'{base}^(2^{j}) mod {number}').control()
        circuit.append(gate, [j] + list(range(precision, precision + work)))
    circuit.compose(inverse_qft(precision), range(precision), inplace=True)
    return circuit, precision


def factor(number=15, base=2, shots=512, seed=42):
    if not 4 <= number <= 21 or not 1 < base < number or not 1 <= shots <= 100000:
        raise ValueError('Demo supports 4 <= N <= 21, 1 < base < N, and 1..100000 shots.')
    divisor = math.gcd(base, number)
    if divisor > 1:
        return {'number': number, 'base': base, 'factors': sorted([divisor, number // divisor]),
                'method': 'classical gcd shortcut', 'counts': {}}
    circuit, precision = order_circuit(number, base)
    probabilities = Statevector.from_instruction(circuit).probabilities(qargs=list(range(precision)))
    measurements = np.random.default_rng(seed).choice(len(probabilities), size=shots, p=probabilities / probabilities.sum())
    counts = Counter(int(x) for x in measurements)
    factors, order = None, None
    for measured, _ in counts.most_common():
        if measured == 0:
            continue
        denominator = Fraction(measured, 2 ** precision).limit_denominator(number).denominator
        # A measured phase can reduce k/r; try its denominator's small multiples.
        for candidate in range(denominator, number + 1, denominator):
            if candidate % 2 or pow(base, candidate, number) != 1:
                continue
            root = pow(base, candidate // 2, number)
            for d in (math.gcd(root - 1, number), math.gcd(root + 1, number)):
                if 1 < d < number:
                    factors, order = sorted([d, number // d]), candidate
                    break
            if factors:
                break
        if factors:
            break
    return {'number': number, 'base': base, 'factors': factors, 'order_candidate': order,
            'method': 'Qiskit statevector phase estimation', 'qubits': circuit.num_qubits,
            'shots': shots, 'seed': seed, 'counts': dict(sorted(counts.items())),
            'status': 'factored' if factors else 'no useful factor; choose another base or increase shots'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--number', type=int, default=15)
    parser.add_argument('--base', type=int, default=2)
    parser.add_argument('--shots', type=int, default=512)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=Path('reports/quantum'))
    args = parser.parse_args()
    result = factor(args.number, args.base, args.shots, args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    if result['counts']:
        circuit, _ = order_circuit(args.number, args.base)
        (args.output / 'circuit.txt').write_text(str(circuit.draw(output='text')), encoding='utf-8')
    print(json.dumps(result, indent=2))
