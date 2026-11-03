# Small Shor simulation

```powershell
python -m quantum.main --number 15 --base 2
python -m quantum.main --number 21 --base 2
```

The circuit uses controlled modular multiplication and an inverse QFT built from Hadamard, controlled-phase, and swap gates. Qiskit simulates the statevector. Sampled phases feed into continued fractions to recover candidate periods and factors.

Inputs are limited to N=4..21 because the modular gates use dense matrices. This is a small simulation, with no quantum hardware run or practical speedup. Prime inputs and some bases may produce no factors. Successful outputs contain two factors, which need not both be prime.

Results are saved as `result.json` and `circuit.txt`.

Reference: [Shor tutorial](https://qiskit.qotlabs.org/docs/tutorials/shors-algorithm).
