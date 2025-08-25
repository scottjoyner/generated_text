# HF Backend (Postgres + Neo4j + FastAPI)

Ingest scraped Hugging Face model JSON into **Postgres** and **Neo4j**, then query with a **FastAPI** service.

## Quick start

1) **Set env vars** (create `.env` at repo root):

```
POSTGRES_DSN=postgresql+psycopg2://user:pass@localhost:5432/hfdb
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
```

2) **Create DBs**:
- Postgres: create the `hfdb` database.
- Neo4j: start local instance; open browser and ensure credentials match.

3) **Install deps** (preferably in a venv):
```
pip install -e .
```

4) **Ingest** your data (accepts `.jsonl` files or directories of `.json` / `.jsonl`):
```
python -m app.ingest --path /path/to/hf_models_out/models_full.jsonl
# or
python -m app.ingest --path /path/to/hf_models_out/cache --recursive
```

5) **Run API**:
```
uvicorn app.main:create_app --reload
```

Then open http://localhost:8000/docs

## What it stores

**Postgres (normalized + raw JSONB):**
- `models` *(core metadata + raw)*
- `authors`, `tags`, `model_tags` (many‑to‑many)
- `siblings` (files), `spaces` (HF Spaces that reference the model)

**Neo4j graph:**
- Nodes: `Model`, `Author`, `Tag`, `License`, `Pipeline`, `Space`, `File`, `Library`
- Rels: `AUTHORED_BY`, `HAS_TAG`, `HAS_LICENSE`, `HAS_PIPELINE`, `APPEARS_IN_SPACE`, `HAS_FILE`, `USES_LIBRARY`

## Example queries

- `GET /models?tag=gguf&author=google&sort=downloads&order=desc`
- `GET /models/{id}` (e.g. `google/gemma-2b`)
- `GET /tags` (top tags & counts)
- `GET /authors` (authors & counts)
- `GET /similar/{id}` (graph: models sharing tags)

## Notes
- Uses safe, simple filters & pagination.
- Adds reasonable indexes for common filters.
