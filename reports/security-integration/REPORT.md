# Security integration results

Tested on Windows 11 x64 with Python 3.12.14. All scan targets in this run were temporary loopback servers. The focused security suite passed all 12 tests in 2.87 seconds, with `SECURITY_NATIVE` set to the compiled C worker.

## Native TCP worker

The C worker was compiled with Zig 0.16.0 using `-O2 -Wall -Wextra -target x86_64-windows-gnu` and `-lws2_32`. The executable SHA-256 is recorded in [results.json](results.json). The executable is not bundled; build instructions are in [the project README](../../security/README.md).

Python and C used two target names (`127.0.0.1` and `localhost`), the same eight ports, two host workers, and a 100 ms timeout. Four ports had listeners; four were reserved but not listening. Both backends found exactly the expected open endpoints in every round. Results for `localhost` also include its resolved IPv6 address where available.

Ten measured rounds followed one warmup round. Backend order alternated. Timings include DNS resolution, process startup, connections and output parsing.

| Backend | Median end-to-end time |
|---|---:|
| Python | 1300.33 ms |
| C worker through Python | 1340.09 ms |

C was about 3.1% slower in this workload. Moving socket calls into native code does not remove connection waits, and the native path adds process startup. These results do not establish a speedup. CPU frequency and background activity were not controlled; no significance test was performed. Raw timings are in `results.json`.

## Nmap

Nmap 7.993 identified the temporary HTTP server as `http`, product `BaseHTTPServer`, version `0.6`, with `Python 3.12.14` as extra information. The result records `method=probed` and confidence 10. The scanner used TCP connect scanning with version detection and XML parsing.

The current official Windows installer was downloaded from [nmap.org](https://nmap.org/download.html), its Authenticode signature was valid, and its files were extracted into a local workspace. The installer and Npcap drivers were not run. Nmap warned that Npcap functions were unavailable and used connect mode. Raw-packet scanning and OS detection were not tested.

## HTTPS and providers

The HTTPS integration test fetched title and description from a temporary local TLS server using a generated certificate explicitly trusted by the test client. The same certificate was rejected by the default trust store. Production TLS verification remains enabled.

Provider tests cover missing keys, domain/IP endpoint routing, authentication header placement and HTTP 429 result preservation. They use fixtures and make no requests to Shodan or VirusTotal. Neither provider key was configured, so live API integration remains unverified. The Rust worker also remains unbuilt in this environment.

## Reproduce

```powershell
python -m security.lab --native PATH_TO_C_WORKER --rounds 10 --nmap-dir PATH_TO_NMAP
$env:SECURITY_NATIVE = 'PATH_TO_C_WORKER'
python -m pytest tests/test_security.py tests/test_security_integration.py -q
```

Local sockets and writable temporary directories must be permitted. The lab closes its listeners after the run and does not scan external systems.
