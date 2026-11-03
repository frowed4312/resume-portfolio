# Security inventory

```powershell
python -m security.main --targets 127.0.0.1 --allowlist security/allowlist.txt --ports 80,443 --mode tcp
python -m security.main --targets 127.0.0.1 --allowlist security/allowlist.txt --ports 80,443 --mode nmap
```

Add authorized hosts to the allowlist before scanning. TCP mode checks connections. Nmap mode requires Nmap on PATH and parses service/version XML from `-sT -sV --version-light`. There is no CIDR expansion or exploitation.

The scanner supports up to 16 workers, resolves targets once, and passes pinned IPs to scanners. Subprocesses use argument lists without a shell. Errors are recorded per target. A missing open port may mean closed, filtered, or timed out; it is not a vulnerability assessment. DNS timing depends on the OS resolver.

Add `--web` to read HTTPS page titles and descriptions. Fetches are limited to 500 KB and ten seconds, with no redirects, JavaScript execution, or crawling.

## Optional providers

Enable `--providers shodan virustotal` with your own `SHODAN_API_KEY` and `VIRUSTOTAL_API_KEY` environment variables. Enabling a provider sends the target to that service. Keys are excluded from source and API error output. HTTP 429 responses are retained without immediate retries.

## Native workers

The C worker uses nonblocking TCP connects with a per-port deadline. It accepts numeric IPv4/IPv6 addresses, validates ports and timeout values before connecting, and prints only open ports. Python retains the allowlist, DNS resolution, and bounded host concurrency.

Build with CMake and a C compiler:

```powershell
cmake -S security/native -B build/security-native
cmake --build build/security-native --config Release
python -m security.main --targets 127.0.0.1 --allowlist security/allowlist.txt --ports 80,443 --mode c --native build/security-native/Release/tcp-probe.exe
```

Single-configuration generators place the executable directly under `build/security-native/`. On Linux, the executable has no `.exe` suffix. A direct Windows build with Zig is also supported:

```powershell
New-Item -ItemType Directory -Force build | Out-Null
zig cc -O2 -Wall -Wextra -target x86_64-windows-gnu security/native/tcp_probe.c -lws2_32 -o build/tcp-probe.exe
```

The original Rust worker remains available:

```powershell
cargo build --release --manifest-path security/native/Cargo.toml
python -m security.main --targets 127.0.0.1 --allowlist security/allowlist.txt --ports 80,443 --mode rust --native security/native/target/release/tcp-probe.exe
```

The C worker has been built and tested on Windows x64. The Rust worker has not been built in this environment. Other platforms still need build verification.

## Local integration checks

```powershell
python -m security.lab --native build/tcp-probe.exe --rounds 10 --nmap-dir PATH_TO_NMAP
```

The lab creates temporary loopback listeners and compares Python and C on the same ports, targets, timeout and worker count. Timings include DNS, process startup and output parsing. It alternates backend order after a warmup and verifies every scan against the known listening ports. Optional Nmap verification identifies a temporary local HTTP server. There are no external scan targets.

Set `SECURITY_NATIVE` to the compiled C executable when running `tests/test_security_integration.py`. These tests cover native input validation, multiple local target names, and HTTPS fetching with a temporary trusted certificate; untrusted TLS is rejected. Provider fixtures check missing credentials, URL/header routing and rate-limit results without calling Shodan or VirusTotal. Live provider integration still requires account credentials and remains unverified.

See [integration results](../reports/security-integration/REPORT.md) for the recorded run and limitations.

References: [Nmap XML](https://nmap.org/book/output-formats-xml-output.html), [Shodan](https://developer.shodan.io/api), [VirusTotal](https://docs.virustotal.com/reference/domain-info).
