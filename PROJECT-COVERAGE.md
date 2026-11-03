# Project coverage

This page maps the project descriptions to working code and recorded evidence. It distinguishes implemented integrations from services that still need a live run.

| Project | Implementation and evidence | Limits |
|---|---|---|
| Anomaly detection | Statistical scoring, Isolation Forest, and PyTorch autoencoders on synthetic sensors and [KDD network connection records](reports/network-anomaly/REPORT.md). Validation selects thresholds and model settings. Reports include precision, recall, F1, ROC-AUC, predictions, and plots. | KDD is a historical simulated-intrusion benchmark. Its split is random and feature-disjoint, not temporal. Sensor data uses a separate chronological split. No modern enterprise deployment evaluation. |
| Mini Shor | Explicit inverse QFT gates, modular multiplication, period recovery, and Qiskit simulation. Tests recover factors of 15 and 21. Source and reports are public in this repository. | Dense statevector simulation, limited to N=21. No quantum hardware execution or practical speedup claim. |
| PQC benchmark | Python and C harnesses call liboqs; classical algorithms use cryptography/OpenSSL. [Security-reference comparison](reports/security-levels/REPORT.md) records sizes, timings, and matching signature-operation ratios for six algorithms. | Comparisons use a coarse 128-bit classical reference tier. PQC categories remain distinct, and RSA/ECC do not provide equivalent quantum security. Key encodings differ. |
| Security inventory | Concurrent allowed-host scans, Nmap service parsing, native workers, HTTPS metadata, and Shodan/VirusTotal adapters. See the [security README](security/README.md) for fresh integration and benchmark evidence. | Third-party scans are not part of the tests. Live provider lookups require account credentials. Rust and C runtime coverage are documented separately. |
| Local task agent | Planner/worker contexts, bounded tool calls, note retrieval, SQLite conversation/run state, deterministic demo, and an Ollama adapter. | Intentionally local-only. OpenAI/Anthropic SDK integration is deferred. HTTP fixtures test the protocol, not actual model inference or answer quality. |

## Describing the cryptography comparison

“Compared against RSA and ECC using documented classical security baselines and NIST PQC categories” describes the measurement more precisely than “equivalent security levels.” No benchmark can make RSA/ECC quantum resistant by choosing a larger key.

## Scope

This repository covers the five projects. It does not establish research employment, publications, challenge rankings, certifications, or contributions to other repositories.
