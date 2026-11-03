# Python wrapper vs C: liboqs benchmark

Windows x64; same DLL; message 312 bytes; 5 rounds x 200 samples per operation/language; 20 warmups per batch.

Reported latency is the median of batch medians. Speedup = Python / C (greater than 1 favors C).

| Algorithm | Operation | Python µs | C µs | Speedup | Time saved |
|---|---|---:|---:|---:|---:|
| ML-KEM-512 | keygen | 104.85 | 102.50 | 1.02x | 2.2% |
| ML-KEM-512 | encapsulate | 108.10 | 104.40 | 1.04x | 3.4% |
| ML-KEM-512 | decapsulate | 26.00 | 23.75 | 1.09x | 8.7% |
| ML-DSA-44 | keygen | 149.00 | 145.80 | 1.02x | 2.1% |
| ML-DSA-44 | sign | 307.15 | 294.00 | 1.04x | 4.3% |
| ML-DSA-44 | verify | 66.30 | 62.70 | 1.06x | 5.4% |
| SLH_DSA_PURE_SHA2_128F | keygen | 1004.50 | 958.45 | 1.05x | 4.6% |
| SLH_DSA_PURE_SHA2_128F | sign | 19683.30 | 18675.65 | 1.05x | 5.1% |
| SLH_DSA_PURE_SHA2_128F | verify | 1117.95 | 1080.10 | 1.04x | 3.4% |

## Interpretation and limits

Both paths execute the same C cryptographic implementation. This measures Python-wrapper versus direct-C harness overhead, not Python versus C implementations of the algorithms.
C reuses buffers; the Python wrapper allocates/copies Python/ctypes buffers. Those costs are included. Library object setup, process startup, output serialization, and post-operation correctness checks are outside the measured regions.
Keys and signing randomness are fresh, not identical. Order alternates, but CPU frequency, scheduling and background load remain uncontrolled. Batch speedup ranges and all raw samples are in results.json. No claim of statistical significance or whole-application speedup.
C performs successful signature verification and KEM agreement checks. Python additionally checks rejection of a modified message outside the timed region.
Historical native CSVs in reports/pqc used the previous 16-byte message. Use this new comparison for matched workloads.
