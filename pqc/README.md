# Cryptography benchmarks

```powershell
python -m pqc.main --iterations 20
```

The benchmark records raw timings, median, mean, p95, and key/ciphertext/signature sizes. Secret keys are not saved. Classical operations use cryptography/OpenSSL: RSA-PSS-3072, ECDSA-P256, and ECDH-P256. Signature verification, modified-message rejection, and shared-secret checks run outside timed regions.

PQC operations use liboqs: ML-KEM-512, ML-DSA-44, and SLH_DSA_PURE_SHA2_128F. Missing libraries or algorithms are reported as unavailable.

## Native runtime

Windows x64 builds of `liboqs.dll` and `oqs_bench.exe` are included under `runtime/liboqs/bin/`. Install the wrapper with `python -m pip install -r requirements-native.txt`. Python finds the bundled DLL automatically. On other systems, build liboqs and set `OQS_INSTALL_PATH` to its installation directory.

```powershell
runtime/liboqs/bin/oqs_bench.exe kem ML-KEM-512 20
runtime/liboqs/bin/oqs_bench.exe sig ML-DSA-44 20
runtime/liboqs/bin/oqs_bench.exe sig SLH_DSA_PURE_SHA2_128F 20
```

To build the C harness with a compiler and installed liboqs:

```powershell
cmake -S pqc/native -B build/pqc -DCMAKE_PREFIX_PATH=PATH_TO_LIBOQS
cmake --build build/pqc --config Release
```

## Python and C comparison

```powershell
python -m pqc.compare --rounds 5 --iterations 200 --warmup 20
```

This comparison uses the bundled Windows runtime, identical 312-byte messages, matching warmups, and alternating run order. Both paths call the same C cryptography library. The difference includes wrapper calls, allocation, and copying; C reuses buffers.

Read [the summary](../reports/pqc-comparison/SUMMARY.md), `REPORT.md`, and raw `results.json` under `reports/pqc-comparison/`. Older native CSVs in `reports/pqc/` used 16-byte messages and should not be used for this comparison.

## Reading the results

Run a fresh comparison with explicit security references:

```powershell
python -m pqc.security_compare --iterations 30
```

The [security comparison](../reports/security-levels/REPORT.md) includes raw measurements, serialized sizes, and ratios for matching signature operations. Algorithms are grouped by a coarse 128-bit classical reference tier, while NIST categories 1 and 2 remain distinct. ECDH and KEM timings appear separately because their operations differ. The JSON report checks the measured liboqs categories against the expected profiles and marks missing algorithms as partial results.

Python timings include FFI overhead. RSA key generation varies substantially, so use more iterations on the same machine for comparisons. The main benchmark uses one warmup; the comparison defaults to twenty per batch. The native harness uses a monotonic timer.

RSA-3072 and P256 provide roughly 128-bit classical strength. PQC results record NIST categories; ML-DSA-44 is category 2. These are not equivalent quantum-security baselines, and ECDH and KEM operations differ. Classical keys use DER while PQC keys use raw encodings, so size comparisons include different encoding overheads.

References: [liboqs-python](https://github.com/open-quantum-safe/liboqs-python), [NIST SP 800-57](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-57pt1r5.pdf).
