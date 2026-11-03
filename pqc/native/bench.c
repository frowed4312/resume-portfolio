/* Native liboqs timing harness. Output CSV; secret memory is securely freed. */
#define _POSIX_C_SOURCE 200809L
#include <oqs/oqs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
static double now_us(void) { LARGE_INTEGER f, t; QueryPerformanceFrequency(&f); QueryPerformanceCounter(&t); return (double)t.QuadPart * 1e6 / f.QuadPart; }
#else
#include <time.h>
static double now_us(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e6 + t.tv_nsec / 1e3; }
#endif

int main(int argc, char **argv) {
    if (argc != 4 && argc != 5) { fprintf(stderr, "Usage: oqs_bench kem|sig algorithm iterations [warmup]\n"); return 2; }
    char *end = NULL; long count = strtol(argv[3], &end, 10);
    if (*end || count < 1 || count > 100000) return 2;
    long warmup = 1;
    if (argc == 5) { warmup = strtol(argv[4], &end, 10); if (*end || warmup < 0 || warmup > 10000) return 2; }
    int kem_mode = strcmp(argv[1], "kem") == 0;
    if (!kem_mode && strcmp(argv[1], "sig") != 0) return 2;
    OQS_init();
    OQS_KEM *kem = kem_mode ? OQS_KEM_new(argv[2]) : NULL;
    OQS_SIG *sig = kem_mode ? NULL : OQS_SIG_new(argv[2]);
    if (!kem && !sig) { fprintf(stderr, "Algorithm unavailable\n"); OQS_destroy(); return 3; }
    size_t pk_len = kem ? kem->length_public_key : sig->length_public_key;
    size_t sk_len = kem ? kem->length_secret_key : sig->length_secret_key;
    size_t payload_len = kem ? kem->length_ciphertext : sig->length_signature;
    unsigned char *pk = malloc(pk_len), *sk = malloc(sk_len), *payload = malloc(payload_len);
    unsigned char *ss = kem ? malloc(kem->length_shared_secret) : NULL;
    unsigned char *other = kem ? malloc(kem->length_shared_secret) : NULL;
    int status = 1;
    if (!pk || !sk || !payload || (kem && (!ss || !other))) goto cleanup;
    puts("algorithm,iteration,keygen_us,encapsulate_or_sign_us,decapsulate_or_verify_us,pk_bytes,sk_bytes,payload_bytes,message_bytes");
    const unsigned char phrase[] = "resume portfolio cryptography benchmark";
    unsigned char message[(sizeof(phrase)-1)*8];
    for (int j = 0; j < 8; ++j) memcpy(message+j*(sizeof(phrase)-1), phrase, sizeof(phrase)-1);
    for (long i = -warmup; i < count; ++i) {
        double start = now_us();
        OQS_STATUS ok = kem ? OQS_KEM_keypair(kem, pk, sk) : OQS_SIG_keypair(sig, pk, sk);
        double keygen = now_us() - start;
        if (ok != OQS_SUCCESS) goto cleanup;
        size_t used = payload_len; start = now_us();
        ok = kem ? OQS_KEM_encaps(kem, payload, ss, pk) : OQS_SIG_sign(sig, payload, &used, message, sizeof(message), sk);
        double op1 = now_us() - start;
        if (ok != OQS_SUCCESS) goto cleanup;
        start = now_us();
        ok = kem ? OQS_KEM_decaps(kem, other, payload, sk) : OQS_SIG_verify(sig, message, sizeof(message), payload, used, pk);
        double op2 = now_us() - start;
        if (ok != OQS_SUCCESS || (kem && memcmp(ss, other, kem->length_shared_secret))) goto cleanup;
        if (i >= 0) printf("%s,%ld,%.3f,%.3f,%.3f,%zu,%zu,%zu,%zu\n", argv[2], i, keygen, op1, op2, pk_len, sk_len, used, sizeof(message));
    }
    status = 0;
cleanup:
    free(pk); free(payload); OQS_MEM_secure_free(sk, sk_len);
    if (kem) { OQS_MEM_secure_free(ss, kem->length_shared_secret); OQS_MEM_secure_free(other, kem->length_shared_secret); }
    OQS_KEM_free(kem); OQS_SIG_free(sig); OQS_destroy(); return status;
}
