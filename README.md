# generated_text — mixed research and web/graph prototypes

A **collection of heterogeneous exploratory files**, not a packaged text-generation model or a single deployment. The default branch includes Python and Node scripts, HTML/Pug templates, Cypher files, data-ingest experiments, report generation, and research notes.

## Source navigation

- `*.cy` — Cypher scripts or examples; inspect them before use on a graph database.
- `neo4j_ingestion.py`, `py2neo.py`, `fastcyAPI.py` — Neo4j-related experiments.
- `app.py`, `app.js`, `cli.py`, `generate.py`, `report.py` — distinct Python/JavaScript entry-point candidates whose invocation has not been validated.
- `*.pug`, `*.html` — experimental templates/frontends.
- `setup.py`, `hf/`, `notes/` — mixed setup/research artifacts.

## Operational boundaries

There is **no verified repository-wide dependency installation, test runner, GraphQL/Neo4j connection, model provider, or data-ingest workflow**. Test each independently after reading its source and external side effects. Keep graph writes and file uploads disabled against production resources; use disposable databases and synthetic inputs.

Protect customer/intake forms, credentials, prompts, transcripts, generated artifacts, and original data provenance. For model requests, preserve provider/model identification, request errors, usage estimates, and redacted traces without exposing raw sensitive content.

**Status:** source/tree documentation only. No network calls, graph writes, model runs, or application deployments performed.
