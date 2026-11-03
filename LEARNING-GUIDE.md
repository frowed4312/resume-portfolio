# Experiment notes

## Anomaly detection

Run `./run-local.ps1 anomaly` and compare the plot with `metrics.json`. Change the seed or supply a CSV. Check how validation selects the threshold and how precision and recall move together. Keep scaling separate from test data. A useful extension is rolling-origin evaluation on real sensor readings.

For network records, follow `anomaly/README.md` to run `python -m anomaly.network`. Check the split identifiers for overlap and compare the validation scores with the held-out metrics. KDD has no timestamp column, so this experiment uses a random split rather than the sensor experiment's chronological split.

## Quantum factoring

Run `./run-local.ps1 quantum`, then try N=21 and different bases. Compare `circuit.txt` with `result.json`. Trace the path from modular period to phase samples, continued fractions, and gcd. Dense simulation becomes expensive quickly.

## Cryptography

Run `./run-local.ps1 pqc` and compare median and p95 across larger sample counts. Keep signature, KEM, and ECDH results separate. Check key encodings and security categories before comparing sizes. Use `python -m pqc.compare` for the matched Python/C workload.

Run `python -m pqc.security_compare` for explicit classical/PQC reference tables and signature ratios. Review why a shared classical reference tier does not imply the same quantum resistance.

## Security inventory

Start with a local server and `./run-local.ps1 security`. Add Nmap for service identification. Keep targets in the allowlist. Compare current scan results with historical provider data; closed ports and timeouts do not establish that a host has no vulnerabilities.

## Local agent

Run `./run-local.ps1 agent`, add notes, and inspect which chunks retrieval selects. Try separate session names. Once Ollama is installed, compare its answers with the deterministic demo. Check citations, tool limits, and report paths. Lexical retrieval can miss relevant material that uses different wording.
