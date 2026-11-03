# Resume projects

My collection of small projects in machine learning, quantum computing, cryptography, security tooling, and local agents. Each project runs from the command line and includes example results.

| Project | What it does |
|---|---|
| [Anomaly detection](anomaly/README.md) | Compares three detectors on sensor data and KDD network connection records. |
| [Quantum factoring](quantum/README.md) | Simulates small Shor circuits with Qiskit. |
| [PQC benchmarks](pqc/README.md) | Measures cryptographic operations and compares Python wrapper overhead with C. |
| [Security inventory](security/README.md) | Checks allowed hosts with TCP, Nmap, or native workers. |
| [Local agent](agent/README.md) | Searches notes and writes reports, with an optional Ollama backend. |

## Setup

Tested with Python 3.12 on Windows x64. Run these commands from the repository root:

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-native.txt
python -m pytest -q
```

For CPU-only PyTorch, install `torch` from https://download.pytorch.org/whl/cpu before installing the requirements.

## Run a project

```powershell
python -m anomaly.main
python -m quantum.main --number 15 --base 2
python -m pqc.main --iterations 5
python -m security.main --targets 127.0.0.1 --allowlist security/allowlist.txt --ports 80,443
python -m agent.main --mode demo
```

On Windows, `./run-local.ps1 anomaly` is a shortcut. Replace `anomaly` with `quantum`, `pqc`, `security`, `agent`, or `test`.

Results go into `reports/`. The agent demo needs no model or API key; Ollama mode needs a separately installed local model.

The [Python/C comparison](reports/pqc-comparison/SUMMARY.md) includes timing data and a plot. Run it again with `python -m pqc.compare`. A separate [security-reference comparison](reports/security-levels/REPORT.md) pairs classical and PQC signature operations and keeps their security assumptions explicit.

The [network anomaly experiment](reports/network-anomaly/REPORT.md) includes held-out scores, raw predictions, and split identifiers. See [project coverage](PROJECT-COVERAGE.md) for the implementation and evidence behind each project.

See [experiment notes](LEARNING-GUIDE.md) for things to try and [verification](VERIFICATION.md) for tested behavior and remaining gaps. These are learning projects using synthetic sensors, an archived intrusion benchmark, and local experiments rather than production evaluations.
