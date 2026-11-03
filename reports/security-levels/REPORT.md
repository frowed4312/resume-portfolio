# Cryptography comparison by security reference

Status: complete. Measured at 2026-10-30T22:58:31.084347+00:00.

The algorithms below share a coarse 128-bit classical reference tier. Their quantum security differs. NIST categories describe reference attack problems, not interchangeable bit counts.

| Algorithm | Role | PQC category | Reference | Quantum resistant |
|---|---|---:|---|---|
| RSA-PSS-3072 | signature | N/A | RSA-3072 classical estimate | No |
| ECDSA-P256 | signature | N/A | P-256 classical estimate | No |
| ECDH-P256 | key agreement | N/A | P-256 classical estimate | No |
| ML-KEM-512 | KEM | 1 | AES-128 key search | Yes |
| ML-DSA-44 | signature | 2 | SHA-256 collision search | Yes |
| SLH_DSA_PURE_SHA2_128F | signature | 1 | AES-128 key search | Yes |

## Operation timings

Medians in microseconds. Every row includes a correctness check outside the timed region. Raw samples are in measurements.json.

| Algorithm | Operation | Samples | Median us | p95 us |
|---|---|---:|---:|---:|
| RSA-PSS-3072 | keygen | 30 | 199998.50 | 572810.84 |
| RSA-PSS-3072 | sign | 30 | 3716.35 | 6228.58 |
| RSA-PSS-3072 | verify | 30 | 149.00 | 207.13 |
| ECDSA-P256 | keygen | 30 | 25.55 | 42.10 |
| ECDSA-P256 | sign | 30 | 44.65 | 64.23 |
| ECDSA-P256 | verify | 30 | 93.00 | 131.81 |
| ECDH-P256 | keygen | 30 | 23.90 | 38.39 |
| ECDH-P256 | exchange | 30 | 75.30 | 82.67 |
| ML-KEM-512 | keygen | 30 | 177.05 | 240.03 |
| ML-KEM-512 | encapsulate | 30 | 176.25 | 271.38 |
| ML-KEM-512 | decapsulate | 30 | 42.85 | 58.16 |
| ML-DSA-44 | keygen | 30 | 299.95 | 392.96 |
| ML-DSA-44 | sign | 30 | 573.25 | 858.37 |
| ML-DSA-44 | verify | 30 | 107.55 | 125.04 |
| SLH_DSA_PURE_SHA2_128F | keygen | 30 | 1515.20 | 1857.19 |
| SLH_DSA_PURE_SHA2_128F | sign | 30 | 29467.85 | 38809.36 |
| SLH_DSA_PURE_SHA2_128F | verify | 30 | 1704.85 | 2856.11 |

## Serialized sizes

| Algorithm | Public key | Private key | Signature | Ciphertext | Encoding |
|---|---:|---:|---:|---:|---|
| RSA-PSS-3072 | 422 | 1794 | 384 | - | DER SPKI / PKCS8 (unencrypted; size only) |
| ECDSA-P256 | 91 | 138 | 71 | - | DER SPKI / PKCS8 (unencrypted; size only) |
| ECDH-P256 | 91 | 138 | - | - | DER SPKI / PKCS8 (unencrypted; size only) |
| ML-KEM-512 | 800 | 1632 | - | 768 | raw liboqs |
| ML-DSA-44 | 1312 | 2560 | 2420 | - | raw liboqs |
| SLH_DSA_PURE_SHA2_128F | 32 | 64 | 17088 | - | raw liboqs |

## Signature comparisons

Ratios are PQC median / classical median. Values below one favor PQC. Only matching signature operations are paired.

| Classical | PQC | Keygen ratio | Sign ratio | Verify ratio |
|---|---|---:|---:|---:|
| RSA-PSS-3072 | ML-DSA-44 | 0.001 | 0.154 | 0.722 |
| RSA-PSS-3072 | SLH_DSA_PURE_SHA2_128F | 0.008 | 7.929 | 11.442 |
| ECDSA-P256 | ML-DSA-44 | 11.740 | 12.839 | 1.156 |
| ECDSA-P256 | SLH_DSA_PURE_SHA2_128F | 59.303 | 659.974 | 18.332 |

## Limits

- RSA and ECC are not quantum resistant. No parameter size gives them PQC-equivalent quantum security.
- Categories 1 and 2 have different reference problems; a shared classical reference tier does not make them the same category.
- ECDH exchange and KEM encapsulation/decapsulation have different roles and security definitions; no cross-operation speedup is calculated.
- Classical keys use DER and PQC keys use raw encoding. Serialized sizes include different overheads.
- Single-machine timings include Python/FFI overhead and are not a statistical performance study.

## Sources

- [classical](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-57pt1r5.pdf)
- [categories](https://csrc.nist.gov/Projects/Post-Quantum-Cryptography/Post-Quantum-Cryptography-Standardization/Evaluation-Criteria/Security-(Evaluation-Criteria))
- [faq](https://csrc.nist.gov/projects/post-quantum-cryptography/faqs)
