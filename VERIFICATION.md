# Verification notes

## Latest integrated check

The expanded suite passed **46 tests in 26.92 seconds**, exit code 0, on Windows x64 / Python 3.12.14. The run included the bundled liboqs runtime and compiled native C scanner; no tests were skipped. Temporary localhost servers and writable test directories were enabled.

```powershell
$env:OQS_INSTALL_PATH = (Resolve-Path runtime/liboqs).Path
$env:SECURITY_NATIVE = 'PATH_TO_COMPILED_C_WORKER'
python -m pytest -q -p no:cacheprovider --basetemp PATH_TO_TEMP_DIRECTORY
```

Separately, the [security lab](reports/security-integration/REPORT.md) verified real Nmap 7.993 service detection and recorded 20 Python/C timing samples. The C worker matched the expected ports but was about 3.1% slower end-to-end in this workload. The saved medians and native binary checksum were independently checked.

The original Windows x64 / Python 3.12.14 baseline passed 35 tests, including native liboqs and the 312-byte C harness regression. Versions are in TESTED-VERSIONS.txt. The expanded project evidence is summarized below.

Run `python -m pytest -q -p no:cacheprovider --basetemp <workspace-temp>` with OQS_INSTALL_PATH pointing to runtime/liboqs. Tests need writable temporary directories and localhost servers. An earlier restricted run had ten temporary-directory setup errors and one TCP failure; the unrestricted run passed without production code changes.

| Project | Checked | Remaining gaps |
|---|---|---|
| Anomaly | Three detectors on synthetic sensors and KDD connection records; chronological sensor split; deduplicated network split; validation tuning and held-out predictions | Historical simulated intrusions, no modern enterprise logs or rolling-origin evaluation |
| Quantum | Inverse QFT against DFT, modular unitary, factors of 15 and 21, CLI export | Dense statevector simulation up to N=21; no hardware runs |
| PQC | Classical and PQC operations, signatures, shared secrets, C harness, explicit security-reference tables, 510 new raw operation samples | Security categories, quantum resistance, and key encodings differ; single-machine timing |
| Security | Local TCP listeners, allowlist, bounds, native C worker, verified HTTPS fetch, provider routing fixtures, and real Nmap HTTP service detection | Live Shodan/VirusTotal calls and Rust execution remain unverified |
| Agent | Retrieval, SQLite persistence, demo CLI, output confinement, HTTP fixture | No real Ollama inference or model-quality evaluation |

## Recorded anomaly results

| Detector | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|
| Robust Z | 0.966 | 1.000 | 0.982 | 1.000 |
| Isolation Forest | 0.697 | 0.821 | 0.754 | 0.985 |
| PyTorch autoencoder | 0.944 | 0.607 | 0.739 | 0.994 |

The synthetic spikes are well separated from the baseline, which favors a simple robust threshold. These numbers do not predict production performance.

## Python/C comparison

The [summary](reports/pqc-comparison/SUMMARY.md) links to the plot and raw results. The recorded dataset contains 18,000 samples. Summary ratios and the bundled DLL SHA-256 were checked. Timings were not rerun for the documentation update.

## Runtime

Create a local .venv using the root README. A Windows x64 liboqs DLL and C harness are included with build metadata and upstream notices. Other platforms need their own native build.

## Earlier English documentation update

Fresh verification: 35 tests passed in 23.52 seconds on Windows x64. The restricted run passed 33 tests; two localhost tests failed there and passed with local network access. Python syntax-tree comparison confirmed that source changes affect only comments and docstrings. Local Markdown links resolve, and the project text contains no Thai characters.

## Network experiment audit

The [network report](reports/network-anomaly/REPORT.md) contains a 6,000/2,000/3,000 train/validation/test split. All 11,000 record IDs are unique across partitions. The 3,000 prediction IDs exactly match the test partition. Precision, recall, F1, ROC-AUC, and threshold decisions were independently recomputed from the saved predictions and match metrics.json.

## Security-reference benchmark audit

The [new PQC report](reports/security-levels/REPORT.md) contains 30 samples per operation across six algorithms, totaling 510 raw timings. Median and p95 values were independently recomputed. Categories are checked against the runtime output; missing algorithms produce a partial report. Signature operations are compared only with matching operations. ECDH and KEM results remain separate.
