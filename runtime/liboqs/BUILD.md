# Bundled Windows x64 runtime

Source: https://github.com/open-quantum-safe/liboqs
Commit: 4778aa5044bf119c30df54219fa89357080af27f
liboqs version: 0.16.0
Compiler: Zig 0.16.0 / Clang 21.1.0 targeting x86_64-windows-gnu
Build: Release, shared library, OQS_USE_OPENSSL=OFF, OQS_DIST_BUILD=OFF, OQS_OPT_TARGET=generic.
Minimal algorithms: KEM_ml_kem_512;SIG_ml_dsa_44;SIG_slh_dsa_pure_sha2_128f.

The accompanying oqs_bench.exe is built from pqc/native/bench.c in this project.
Upstream LICENSE.txt is included. This is an educational benchmark runtime, not a validated cryptographic product.
