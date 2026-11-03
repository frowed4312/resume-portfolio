# Local inference check

Tested on November 2, 2026 with Ollama 0.40.13, `qwen3:1.7b` for generation and `all-minilm` for embeddings. Generation used CPU mode with thinking disabled. Model digests and runtime metadata are in `runtime.json`.

```powershell
python -m agent.evaluate --model qwen3:1.7b --embedding-model all-minilm --port 11439 --cpu
```

The final run passed the automated checks for all three tasks:

| Task | Checks | Time |
| --- | --- | --- |
| Explain precision and recall | Retrieves notes, mentions the source and recall | 7.441 s |
| Save a report | Retrieves notes, creates the requested file, includes a source filename | 9.116 s |
| Follow-up after reopening SQLite | Retrieves notes, mentions the source and recall | 10.174 s |

Full answers, plans, retrieved evidence, tool results, and checks are in `local-evaluation.json`. The test uses a temporary database and report directory, so it does not retain the generated report file. The project regression suite passed 62 tests.

During development, generic JSON output produced invalid plans on all three tasks. A schema constrained the planner to the expected list of strings. A later run passed two tasks but saved a report without a source filename. The worker now checks that evidence was retrieved and that the report mentions a retrieved source before allowing the write.

These are development smoke tasks on one short English note, not held-out evaluation. Source mentions do not establish factual correctness. The follow-up confirms that the workflow runs after reopening the store, but does not prove that its answer depends on conversation memory. The final answer describes recall loosely as measuring missed anomalies; more precisely, recall measures the fraction detected, while the false-negative rate measures the fraction missed. Results and timings can vary between runs. Empty-corpus reasoning, adversarial documents, longer conversations, and broader task completion are not evaluated here.
