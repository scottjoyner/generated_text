import argparse, json, os, sys, pathlib, datetime
from typing import Iterable, Iterator

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import engine, SessionLocal, Base, ensure_indexes
from .models import Author, Model, Tag, ModelTag, Sibling, Space, ModelSpace
from .neo import driver, ensure_schema
from .utils import split_repo_id, resolve_license

def iter_records(path: str, recursive: bool=False) -> Iterator[dict]:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    def read_jsonl(fpath: pathlib.Path):
        with fpath.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception as e:
                    print(f"[WARN] Bad JSONL line in {fpath}: {e}", file=sys.stderr)

    def read_json(fpath: pathlib.Path):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(data, dict):
                yield data
        except Exception as e:
            print(f"[WARN] Bad JSON in {fpath}: {e}", file=sys.stderr)

    candidates = []
    if p.is_file():
        candidates = [p]
    else:
        if recursive:
            candidates = list(p.rglob("*.json")) + list(p.rglob("*.jsonl"))
        else:
            candidates = list(p.glob("*.json")) + list(p.glob("*.jsonl"))

    for f in candidates:
        if f.suffix == ".jsonl":
            yield from read_jsonl(f)
        elif f.suffix == ".json":
            yield from read_json(f)

def to_dt(val):
    if not val:
        return None
    try:
        # 2024-09-27T12:18:55.000Z
        return datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        return None

def upsert_sql(session: Session, rec: dict):
    repo_id = rec.get("id") or rec.get("modelId")
    if not repo_id:
        return
    author_name, name = split_repo_id(repo_id)
    author_obj = None
    if author_name:
        author_obj = session.scalar(select(Author).where(Author.name == author_name))
        if not author_obj:
            author_obj = Author(name=author_name)
            session.add(author_obj)
            session.flush()

    m = session.get(Model, repo_id)
    if not m:
        m = Model(id=repo_id)
        session.add(m)

    m.author_id = author_obj.id if author_obj else None
    m.name = name
    m.private = bool(rec.get("private", False))
    gated = rec.get("gated")
    m.gated = str(gated) if gated is not None else None
    m.sha = rec.get("sha")
    m.pipeline_tag = rec.get("pipeline_tag")
    m.library_name = rec.get("library_name") or (rec.get("cardData") or {}).get("library_name")
    lic = resolve_license(rec)
    m.license = lic
    m.license_raw = rec.get("license")
    m.downloads = rec.get("downloads")
    m.likes = rec.get("likes")
    m.created_at = to_dt(rec.get("createdAt"))
    m.last_modified = to_dt(rec.get("lastModified"))
    m.used_storage = rec.get("usedStorage")

    card = rec.get("cardData") or {}
    m.card_summary = card.get("summary") or card.get("description")
    m.card_params = card.get("params")
    m.card_model_size = card.get("model_size")
    m.card_datasets = card.get("datasets")
    m.card_languages = card.get("language") or card.get("languages")
    m.config = rec.get("config")
    m.transformers_info = rec.get("transformersInfo")
    m.gguf = rec.get("gguf")
    m.safetensors = rec.get("safetensors")
    m.raw = rec

    # tags (idempotent)
    tags = rec.get("tags") or []
    for t in tags:
        if not isinstance(t, str):
            continue
        tag = session.get(Tag, t) or Tag(name=t)
        session.add(tag)
        # link
        if not session.get(ModelTag, {"model_id": m.id, "tag": t}):
            session.add(ModelTag(model_id=m.id, tag=t))

    # siblings
    siblings = [s.get("rfilename") for s in (rec.get("siblings") or []) if isinstance(s, dict) and s.get("rfilename")]
    existing_sibs = {(s.rfilename) for s in m.siblings}
    for rfn in siblings:
        if rfn not in existing_sibs:
            session.add(Sibling(model_id=m.id, rfilename=rfn))

    # spaces
    spaces = rec.get("spaces") or []
    existing_spaces = {(s.space_name) for s in m.spaces}
    for sp in spaces:
        if sp not in existing_spaces:
            # ensure space
            session.merge(Space(name=sp))
            session.add(ModelSpace(model_id=m.id, space_name=sp))

def upsert_neo(rec: dict):
    repo_id = rec.get("id") or rec.get("modelId")
    if not repo_id:
        return
    author, name = split_repo_id(repo_id)
    lic = resolve_license(rec)
    tags = [t for t in (rec.get("tags") or []) if isinstance(t, str)]
    siblings = [s.get("rfilename") for s in (rec.get("siblings") or []) if isinstance(s, dict) and s.get("rfilename")]
    spaces = rec.get("spaces") or []
    library = rec.get("library_name") or (rec.get("cardData") or {}).get("library_name")
    pipeline = rec.get("pipeline_tag")

    card = rec.get("cardData") or {}

    q = """    MERGE (m:Model {id:$id})
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
    CALL {
      WITH m
      MERGE (a:Author {name:$author})
      MERGE (m)-[:AUTHORED_BY]->(a)
      RETURN 0 as _
    }
    WITH m
    CALL {
      WITH m
      UNWIND $tags as t
      MERGE (tg:Tag {name:t})
      MERGE (m)-[:HAS_TAG]->(tg)
      RETURN 0 as _
    }
    WITH m
    CALL {
      WITH m
      MERGE (l:License {name:coalesce($license,'unknown')})
      MERGE (m)-[:HAS_LICENSE]->(l)
      RETURN 0 as _
    }
    WITH m
    CALL {
      WITH m
      WITH m, $pipeline as pn
      WHERE pn IS NOT NULL
      MERGE (p:Pipeline {name:pn})
      MERGE (m)-[:HAS_PIPELINE]->(p)
      RETURN 0 as _
    }
    WITH m
    CALL {
      WITH m
      WITH m, $library as ln
      WHERE ln IS NOT NULL
      MERGE (l:Library {name:ln})
      MERGE (m)-[:USES_LIBRARY]->(l)
      RETURN 0 as _
    }
    WITH m
    CALL {
      WITH m
      UNWIND $siblings as rf
      MERGE (f:File {name:rf})
      MERGE (m)-[:HAS_FILE]->(f)
      RETURN 0 as _
    }
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

    params = {
        "id": repo_id,
        "name": name,
        "author": author,
        "private": bool(rec.get("private", False)),
        "gated": str(rec.get("gated")) if rec.get("gated") is not None else None,
        "sha": rec.get("sha"),
        "pipeline": pipeline,
        "library": library,
        "license": lic,
        "downloads": rec.get("downloads"),
        "likes": rec.get("likes"),
        "created_at": rec.get("createdAt"),
        "last_modified": rec.get("lastModified"),
        "card_summary": card.get("summary") or card.get("description"),
        "tags": tags,
        "siblings": siblings,
        "spaces": spaces,
    }
    with driver.session() as sess:
        sess.run(q, params)

def main():
    ap = argparse.ArgumentParser(description="Ingest HF JSON into Postgres + Neo4j.")
    ap.add_argument("--path", required=True, help="Path to .jsonl or directory of .json/.jsonl")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders")
    args = ap.parse_args()

    # Create tables
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        ensure_indexes(conn)
    ensure_schema()

    count = 0
    with SessionLocal() as s:
        for rec in iter_records(args.path, recursive=args.recursive):
            try:
                upsert_sql(s, rec)
                upsert_neo(rec)
                count += 1
                if count % 200 == 0:
                    s.commit()
                    print(f"[INGEST] {count} records committed...")
            except Exception as e:
                s.rollback()
                print(f"[ERROR] {e}", file=sys.stderr)
        s.commit()
    print(f"[DONE] Ingested {count} records.")

if __name__ == "__main__":
    main()
