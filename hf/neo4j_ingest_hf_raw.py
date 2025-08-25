#!/usr/bin/env python3
"""
Ingest Hugging Face model JSON (cache/*.json) into Neo4j.

Env:
  NEO4J_URI=bolt://localhost:7687
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=your_password

Usage:
  python neo4j_ingest.py --cache-dir cache
"""

import os, json, argparse, pathlib, sys
from typing import Iterator, Tuple, Optional

# pip install neo4j
from neo4j import GraphDatabase

# ---------- Helpers ----------
def split_repo_id(repo_id: str) -> Tuple[str, str]:
    parts = repo_id.split("/", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("", repo_id)

def resolve_license(detail_json: dict) -> Optional[str]:
    lic = detail_json.get("license")
    if lic:
        return str(lic)
    card = detail_json.get("cardData") or {}
    card_lic = card.get("license")
    if isinstance(card_lic, str) and card_lic.strip():
        return card_lic.strip()
    if isinstance(card_lic, dict):
        for k in ("name", "id", "spdx"):
            v = card_lic.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    for t in (detail_json.get("tags") or []):
        if isinstance(t, str) and t.lower().startswith("license:"):
            return t.split(":", 1)[1].strip()
    return None

def iter_cache_json(cache_dir: str) -> Iterator[dict]:
    p = pathlib.Path(cache_dir)
    if not p.exists():
        raise FileNotFoundError(cache_dir)
    for fp in sorted(p.glob("*.json")):
        try:
            yield json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Skipping {fp.name}: {e}", file=sys.stderr)

# ---------- Schema ----------
CONSTRAINTS = [
    "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT model_id IF NOT EXISTS FOR (m:Model) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT license_name IF NOT EXISTS FOR (l:License) REQUIRE l.name IS UNIQUE",
    "CREATE CONSTRAINT pipeline_name IF NOT EXISTS FOR (p:Pipeline) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT space_name IF NOT EXISTS FOR (s:Space) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT file_name IF NOT EXISTS FOR (f:File) REQUIRE f.name IS UNIQUE",
    "CREATE CONSTRAINT lib_name IF NOT EXISTS FOR (l:Library) REQUIRE l.name IS UNIQUE"
]

FULLTEXT = [
    "CALL db.index.fulltext.createNodeIndex('modelText', ['Model'], ['id','name','card_summary'])",
    "CALL db.index.fulltext.createNodeIndex('tagText', ['Tag'], ['name'])"
]

def ensure_schema(driver):
    with driver.session() as sess:
        for q in CONSTRAINTS:
            sess.run(q)
        for q in FULLTEXT:
            try:
                sess.run(q)
            except Exception:
                pass

# ---------- Upsert ----------
UPSERT = """
MERGE (m:Model {id:$id})
  ON CREATE SET m.name=$name
SET m.private=$private,
    m.gated=$gated,
    m.sha=$sha,
    m.pipeline_tag=$pipeline,
    m.library_name=$library,
    m.license=$license,
    m.downloads=$downloads,
    m.likes=$likes,
    m.created_at=$created_at,
    m.last_modified=$last_modified,
    m.card_summary=$card_summary
WITH m
// Author
CALL {
  WITH m
  WITH m, $author as an
  WHERE an IS NOT NULL AND an <> ''
  MERGE (a:Author {name:an})
  MERGE (m)-[:AUTHORED_BY]->(a)
  RETURN 0 as _
}
// Tags
WITH m
CALL {
  WITH m
  UNWIND $tags as t
  MERGE (tg:Tag {name:t})
  MERGE (m)-[:HAS_TAG]->(tg)
  RETURN 0 as _
}
// License
WITH m
CALL {
  WITH m
  MERGE (l:License {name:coalesce($license,'unknown')})
  MERGE (m)-[:HAS_LICENSE]->(l)
  RETURN 0 as _
}
// Pipeline
WITH m
CALL {
  WITH m
  WITH m, $pipeline as pn
  WHERE pn IS NOT NULL
  MERGE (p:Pipeline {name:pn})
  MERGE (m)-[:HAS_PIPELINE]->(p)
  RETURN 0 as _
}
// Library
WITH m
CALL {
  WITH m
  WITH m, $library as ln
  WHERE ln IS NOT NULL
  MERGE (l:Library {name:ln})
  MERGE (m)-[:USES_LIBRARY]->(l)
  RETURN 0 as _
}
// Files
WITH m
CALL {
  WITH m
  UNWIND $siblings as rf
  MERGE (f:File {name:rf})
  MERGE (m)-[:HAS_FILE]->(f)
  RETURN 0 as _
}
// Spaces
WITH m
CALL {
  WITH m
  UNWIND $spaces as sp
  MERGE (s:Space {name:sp})
  MERGE (m)-[:APPEARS_IN_SPACE]->(s)
  RETURN 0 as _
}
RETURN m.id as id
"""

def upsert_model(driver, rec: dict):
    repo_id = rec.get("id") or rec.get("modelId")
    if not repo_id:
        return
    author, name = split_repo_id(repo_id)
    lic = resolve_license(rec)
    card = rec.get("cardData") or {}
    params = {
        "id": repo_id,
        "name": name,
        "author": author,
        "private": bool(rec.get("private", False)),
        "gated": str(rec.get("gated")) if rec.get("gated") is not None else None,
        "sha": rec.get("sha"),
        "pipeline": rec.get("pipeline_tag"),
        "library": rec.get("library_name") or card.get("library_name"),
        "license": lic,
        "downloads": rec.get("downloads"),
        "likes": rec.get("likes"),
        "created_at": rec.get("createdAt"),
        "last_modified": rec.get("lastModified"),
        "card_summary": card.get("summary") or card.get("description"),
        "tags": [t for t in (rec.get("tags") or []) if isinstance(t, str)],
        "siblings": [s.get("rfilename") for s in (rec.get("siblings") or [])
                     if isinstance(s, dict) and s.get("rfilename")],
        "spaces": rec.get("spaces") or [],
    }
    with driver.session() as sess:
        sess.run(UPSERT, params)

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Ingest HF cache/*.json into Neo4j")
    ap.add_argument("--cache-dir", default="cache")
    args = ap.parse_args()

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd  = os.environ.get("NEO4J_PASSWORD")
    if not pwd:
        print("Set NEO4J_PASSWORD", file=sys.stderr)
        sys.exit(2)

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    ensure_schema(driver)

    count = 0
    try:
        for rec in iter_cache_json(args.cache_dir):
            upsert_model(driver, rec)
            count += 1
            if count % 200 == 0:
                print(f"[UPSERT] {count} records")
        print(f"[DONE] Ingested {count} records into Neo4j.")
    finally:
        driver.close()

if __name__ == "__main__":
    main()
