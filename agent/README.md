# Local task agent

```powershell
python -m agent.main --mode demo --task "Explain anomaly precision and recall"
```

Demo mode retrieves note excerpts, adds source references, and saves a Markdown report and SQLite run state. It is deterministic and uses no language model.

To use a local model, start Ollama with an installed model that supports tool calling:

```powershell
python -m agent.main --mode ollama --model YOUR_INSTALLED_MODEL --task "Explain precision and recall using local notes and save a report"
```

The planner uses a JSON schema to return one to four steps. The worker has up to eight calls to `search_notes` and `write_report`. They use separate contexts and can share one model. Requests stay on localhost; no paid API is required. Thinking is disabled for the tested Qwen model; `--cpu` selects CPU generation if needed.

## Notes and memory

Add Markdown files to `agent/notes/`. The default uses 2,048-dimensional lexical HashingVectorizer vectors. For semantic retrieval, install a local embedding model and select it explicitly:

```powershell
$env:OLLAMA_NO_CLOUD = "1"
ollama serve
# In another terminal:
ollama pull qwen3:1.7b
ollama pull all-minilm
python -m agent.main --mode ollama --model qwen3:1.7b --embedding-model all-minilm --db reports/agent/semantic.sqlite3 --task "Explain precision and recall using local notes"
```

SQLite stores chunks and vectors, and retrieval uses exact cosine search. The index records the embedding backend and vector dimension; incompatible settings are rejected. Use a fresh database if you replace a model behind an existing tag. Embedding requests are batched, stay on localhost, reject redirects, and do not silently truncate text. The similarity cutoff is a heuristic, not a calibrated relevance score.

Use `--session NAME` for separate histories. Prompts include the last ten messages; SQLite retains run status and tool traces. Reingesting a filename replaces its chunks. Deleting a source file does not remove its stored chunks, so use a new `--db` path for a fresh corpus.

Reports stay inside the output directory and cannot overwrite existing files. In model mode, a report requires a successful search first. When that search finds evidence, the report must mention at least one retrieved source filename. The tool returns an error for the model to correct if the citation is missing. This checks source presence, not whether every statement follows from it. The worker has no shell or messaging tool. Retrieved documents are treated as data, and model answers still need checking against their sources.

The HTTP contract tests use a local fixture, not an actual model. Run the separate inference smoke evaluation with:

```powershell
python -m agent.evaluate --model qwen3:1.7b --embedding-model all-minilm --cpu
```

This runs three tasks against a short note and saves the full traces and checks to `reports/agent/local-evaluation.json`. It checks retrieval, source mentions, report creation, and a follow-up after reopening SQLite. These checks do not prove factual accuracy or robust reasoning. Model answers and reports still need human review.

Reference: [Ollama tool calling](https://github.com/ollama/ollama/blob/main/docs/capabilities/tool-calling.mdx).
