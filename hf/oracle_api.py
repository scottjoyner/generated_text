
**Endpoints:**
- `GET /health`
- `GET /models` — same filters as Oracle API
- `GET /models/{id}` — detail
- `GET /tags` — facets
- `GET /authors` — facets
- `GET /similar/{id}` — models sharing the most tags
```").strip(), encoding="utf-8")

# Oracle API
(root / "oracle_api.py").write_text(textwrap.dedent("""
#!/usr/bin/env python3
"""
FastAPI for querying Oracle tables created by oracle_ingest.py.

Tables expected:
  authors(author_id PK, name unique)
  models(id PK, author_id FK, name, private, gated, sha, pipeline_tag, library_name, license, license_raw,
         downloads, likes, created_at, last_modified, used_storage,
         card_summary (CLOB), ... raw_json (CLOB), etc.)
  tags(name PK)
  model_tags(model_id, tag) PK
  siblings(model_id, rfilename) PK
  spaces(name PK)
  model_spaces(model_id, space_name) PK
"""
import os
import oracledb
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_DSN = os.getenv("ORACLE_DSN")
POOL_MIN = int(os.getenv("ORACLE_POOL_MIN", "1"))
POOL_MAX = int(os.getenv("ORACLE_POOL_MAX", "8"))
POOL_INC = int(os.getenv("ORACLE_POOL_INC", "1"))

SORT_MAP = {
    "downloads": "m.downloads",
    "likes": "m.likes",
    "last_modified": "m.last_modified",
    "created_at": "m.created_at",
    "id": "m.id",
    "name": "m.name",
}

pool = None

def get_pool():
    global pool
    if pool is None:
        if not (ORACLE_USER and ORACLE_PASSWORD and ORACLE_DSN):
            raise RuntimeError("Set ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN")
        pool = oracledb.create_pool(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN,
                                    min=POOL_MIN, max=POOL_MAX, increment=POOL_INC, homogeneous=True)
    return pool

def dictify(cursor, rows):
    cols = [d[0].lower() for d in cursor.description]
    out = []
    for r in rows:
        obj = {}
        for i, c in enumerate(cols):
            v = r[i]
            if isinstance(v, datetime):
                v = v.isoformat()
            obj[c] = v
        out.append(obj)
    return out

def model_row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    # tags/siblings/spaces come as comma-separated strings; split to arrays
    for k in ("tags","siblings","spaces"):
        if row.get(k):
            row[k] = [x for x in (row[k] or "").split(",") if x]
        else:
            row[k] = []
    return row

def create_app() -> FastAPI:
    app = FastAPI(title="HF Oracle API", version="0.1.0")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/models")
    def models(
        q: Optional[str] = None,
        author: Optional[str] = None,
        tag: Optional[List[str]] = Query(default=None),
        license: Optional[str] = None,
        pipeline: Optional[str] = None,
        min_downloads: Optional[int] = None,
        gated: Optional[str] = None,
        private: Optional[bool] = None,
        sort: str = "downloads",
        order: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ):
        sort_col = SORT_MAP.get(sort, "m.downloads")
        order_sql = "ASC" if (order or "").lower() == "asc" else "DESC"
        offset = max(0, (max(1, page) - 1) * max(1, page_size))
        limit = max(1, page_size)

        # Build filter where clause
        where = ["1=1"]
        binds = {}

        if q:
            where.append("(LOWER(m.id) LIKE :q OR LOWER(m.name) LIKE :q)")
            binds["q"] = f"%{q.lower()}%"
        if author:
            where.append("a.name = :author")
            binds["author"] = author
        if license:
            where.append("m.license = :license")
            binds["license"] = license
        if pipeline:
            where.append("m.pipeline_tag = :pipeline")
            binds["pipeline"] = pipeline
        if min_downloads is not None:
            where.append("m.downloads >= :min_downloads")
            binds["min_downloads"] = min_downloads
        if gated is not None and gated != "":
            where.append("m.gated = :gated")
            binds["gated"] = gated
        if private is not None:
            where.append("m.private = :private")
            binds["private"] = 1 if private else 0

        # For tag AND filter, use EXISTS for each tag
        tag_filters = []
        if tag:
            for idx, t in enumerate(tag):
                key = f"tag{idx}"
                tag_filters.append(f"EXISTS (SELECT 1 FROM model_tags mt{idx} WHERE mt{idx}.model_id = m.id AND mt{idx}.tag = :{key})")
                binds[key] = t

        where_sql = " AND ".join(where + tag_filters)

        filtered_cte = f\"\"\"
          WITH filtered AS (
            SELECT m.id
            FROM models m
            LEFT JOIN authors a ON a.author_id = m.author_id
            WHERE {where_sql}
          )
        \"\"\"

        total_sql = filtered_cte + "SELECT COUNT(*) AS total FROM filtered"
        rows_sql = filtered_cte + f\"\"\"
          SELECT
            m.id,
            a.name AS author,
            m.name,
            m.private,
            m.gated,
            m.sha,
            m.pipeline_tag,
            m.library_name,
            m.license,
            m.downloads,
            m.likes,
            m.created_at,
            m.last_modified,
            (SELECT LISTAGG(mt.tag, ',') WITHIN GROUP (ORDER BY mt.tag) FROM model_tags mt WHERE mt.model_id = m.id) AS tags,
            (SELECT LISTAGG(s.rfilename, ',') WITHIN GROUP (ORDER BY s.rfilename) FROM siblings s WHERE s.model_id = m.id) AS siblings,
            (SELECT LISTAGG(ms.space_name, ',') WITHIN GROUP (ORDER BY ms.space_name) FROM model_spaces ms WHERE ms.model_id = m.id) AS spaces
          FROM models m
          LEFT JOIN authors a ON a.author_id = m.author_id
          JOIN filtered f ON f.id = m.id
          ORDER BY {sort_col} {order_sql} NULLS LAST
          OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        \"\"\"

        binds_rows = dict(binds)
        binds_rows.update({"offset": offset, "limit": limit})

        pool = get_pool()
        with pool.acquire() as conn:
            cur = conn.cursor()
            cur.execute(total_sql, binds)
            total = int(cur.fetchone()[0])
            cur.execute(rows_sql, binds_rows)
            data = [model_row_to_dict(r) for r in dictify(cur, cur.fetchall())]

        return {"items": data, "page": page, "page_size": page_size, "total": total}

    @app.get("/models/{model_id}")
    def model_detail(model_id: str):
        pool = get_pool()
        with pool.acquire() as conn:
            cur = conn.cursor()
            # Core row
            cur.execute(\"\"\"
              SELECT m.id, a.name AS author, m.name, m.private, m.gated, m.sha, m.pipeline_tag, m.library_name,
                     m.license, m.license_raw, m.downloads, m.likes, m.created_at, m.last_modified,
                     m.card_summary, m.raw_json
              FROM models m
              LEFT JOIN authors a ON a.author_id = m.author_id
              WHERE m.id = :id
            \"\"\", {"id": model_id})
            row = cur.fetchone()
            if not row:
                return JSONResponse({"error": "not found"}, status_code=404)
            cols = [d[0].lower() for d in cur.description]
            obj = {cols[i]: (row[i].isoformat() if isinstance(row[i], datetime) else row[i]) for i in range(len(cols))}

            # tags
            cur.execute("SELECT tag FROM model_tags WHERE model_id=:id ORDER BY tag", {"id": model_id})
            tags = [r[0] for r in cur.fetchall()]
            # files
            cur.execute("SELECT rfilename FROM siblings WHERE model_id=:id ORDER BY rfilename", {"id": model_id})
            siblings = [r[0] for r in cur.fetchall()]
            # spaces
            cur.execute("SELECT space_name FROM model_spaces WHERE model_id=:id ORDER BY space_name", {"id": model_id})
            spaces = [r[0] for r in cur.fetchall()]

        obj["tags"] = tags
        obj["siblings"] = siblings
        obj["spaces"] = spaces
        return obj

    @app.get("/tags")
    def tags():
        pool = get_pool()
        with pool.acquire() as conn:
            cur = conn.cursor()
            cur.execute(\"\"\"
              SELECT mt.tag, COUNT(*) AS c
              FROM model_tags mt
              GROUP BY mt.tag
              ORDER BY c DESC, mt.tag
              FETCH FIRST 200 ROWS ONLY
            \"\"\")
            return [{"tag": r[0], "count": int(r[1])} for r in cur.fetchall()]

    @app.get("/authors")
    def authors():
        pool = get_pool()
        with pool.acquire() as conn:
            cur = conn.cursor()
            cur.execute(\"\"\"
              SELECT NVL(a.name, '(unknown)') AS author, COUNT(*) AS c
              FROM models m
              LEFT JOIN authors a ON a.author_id = m.author_id
              GROUP BY NVL(a.name, '(unknown)')
              ORDER BY c DESC, author
              FETCH FIRST 200 ROWS ONLY
            \"\"\")
            return [{"author": r[0], "count": int(r[1])} for r in cur.fetchall()]

    return app

# Allow 'python oracle_api.py' to run the server quickly (dev only)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host=os.getenv("API_HOST","0.0.0.0"), port=int(os.getenv("API_PORT","8090")))
""").strip(), encoding="utf-8")

# Neo4j API
(root / "neo4j_api.py").write_text(textwrap.dedent("""
#!/usr/bin/env python3
"""
FastAPI for querying Neo4j graph created by neo4j_ingest.py.
"""
import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

SORT_MAP = {
    "downloads": "m.downloads",
    "likes": "m.likes",
    "last_modified": "m.last_modified",
    "created_at": "m.created_at",
    "id": "m.id",
    "name": "m.name",
}

driver = None

def get_driver():
    global driver
    if driver is None:
        if not NEO4J_PASSWORD:
            raise RuntimeError("Set NEO4J_PASSWORD")
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return driver

def create_app() -> FastAPI:
    app = FastAPI(title="HF Neo4j API", version="0.1.0")

    @app.on_event("shutdown")
    def _close():
        if driver is not None:
            driver.close()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/models")
    def models(
        q: Optional[str] = None,
        author: Optional[str] = None,
        tag: Optional[List[str]] = Query(default=None),
        license: Optional[str] = None,
        pipeline: Optional[str] = None,
        min_downloads: Optional[int] = None,
        gated: Optional[str] = None,
        private: Optional[bool] = None,
        sort: str = "downloads",
        order: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ):
        d = get_driver()

        sort_exp = SORT_MAP.get(sort, "m.downloads")
        order_sql = "ASC" if (order or '').lower() == "asc" else "DESC"
        skip = max(0, (max(1, page) - 1) * max(1, page_size))
        limit = max(1, page_size)

        # Base filter WHERE (shared across count + rows)
        where_parts = [
            "($q IS NULL OR toLower(m.id) CONTAINS toLower($q) OR toLower(m.name) CONTAINS toLower($q))",
            "($author IS NULL OR a.name = $author)",
            "($license IS NULL OR m.license = $license)",
            "($pipeline IS NULL OR m.pipeline_tag = $pipeline)",
            "($gated IS NULL OR m.gated = $gated)",
            "($private IS NULL OR m.private = $private)",
            "($min_downloads IS NULL OR m.downloads >= $min_downloads)",
            "($tags IS NULL OR ALL(t IN $tags WHERE EXISTS( (m)-[:HAS_TAG]->(:Tag {name: t}) )))"
        ]
        where_sql = " AND ".join(where_parts)

        count_q = f\"\"\"
        MATCH (m:Model)
        OPTIONAL MATCH (m)-[:AUTHORED_BY]->(a:Author)
        WHERE {where_sql}
        RETURN count(DISTINCT m) AS total
        \"\"\"

        rows_q = f\"\"\"
        MATCH (m:Model)
        OPTIONAL MATCH (m)-[:AUTHORED_BY]->(a:Author)
        WHERE {where_sql}
        WITH DISTINCT m, a
        ORDER BY {sort_exp} {order_sql}
        SKIP $skip LIMIT $limit
        OPTIONAL MATCH (m)-[:HAS_TAG]->(tg:Tag)
        OPTIONAL MATCH (m)-[:HAS_FILE]->(f:File)
        OPTIONAL MATCH (m)-[:APPEARS_IN_SPACE]->(s:Space)
        WITH m, a, collect(DISTINCT tg.name) AS tags, collect(DISTINCT f.name) AS siblings, collect(DISTINCT s.name) AS spaces
        RETURN m.id AS id, a.name AS author, m.name AS name, m.private AS private, m.gated AS gated, m.sha AS sha,
               m.pipeline_tag AS pipeline_tag, m.library_name AS library_name, m.license AS license,
               m.downloads AS downloads, m.likes AS likes, m.created_at AS created_at, m.last_modified AS last_modified,
               tags, siblings, spaces
        \"\"\"

        params = {
            "q": q,
            "author": author,
            "license": license,
            "pipeline": pipeline,
            "gated": gated,
            "private": private,
            "min_downloads": min_downloads,
            "tags": tag,
            "skip": skip,
            "limit": limit,
        }

        with d.session() as sess:
            total = sess.run(count_q, params).single()["total"]
            rows = [rec.data() for rec in sess.run(rows_q, params)]
        return {"items": rows, "page": page, "page_size": page_size, "total": total}

    @app.get("/models/{model_id}")
    def model_detail(model_id: str):
        d = get_driver()
        q = \"\"\"
        MATCH (m:Model {id:$id})
        OPTIONAL MATCH (m)-[:AUTHORED_BY]->(a:Author)
        OPTIONAL MATCH (m)-[:HAS_TAG]->(tg:Tag)
        OPTIONAL MATCH (m)-[:HAS_FILE]->(f:File)
        OPTIONAL MATCH (m)-[:APPEARS_IN_SPACE]->(s:Space)
        WITH m, a, collect(DISTINCT tg.name) AS tags, collect(DISTINCT f.name) AS siblings, collect(DISTINCT s.name) AS spaces
        RETURN m.id AS id, a.name AS author, m.name AS name, m.private AS private, m.gated AS gated, m.sha AS sha,
               m.pipeline_tag AS pipeline_tag, m.library_name AS library_name, m.license AS license,
               m.downloads AS downloads, m.likes AS likes, m.created_at AS created_at, m.last_modified AS last_modified,
               tags, siblings, spaces
        \"\"\"
        with d.session() as sess:
            rec = sess.run(q, {"id": model_id}).single()
            if not rec:
                return JSONResponse({"error": "not found"}, status_code=404)
            return rec.data()

    @app.get("/tags")
    def tags():
        d = get_driver()
        q = \"\"\"
        MATCH (m:Model)-[:HAS_TAG]->(t:Tag)
        RETURN t.name AS tag, count(DISTINCT m) AS count
        ORDER BY count DESC, tag
        LIMIT 200
        \"\"\"
        with d.session() as sess:
            return [r.data() for r in sess.run(q)]

    @app.get("/authors")
    def authors():
        d = get_driver()
        q = \"\"\"
        MATCH (m:Model)
        OPTIONAL MATCH (m)-[:AUTHORED_BY]->(a:Author)
        RETURN coalesce(a.name, '(unknown)') AS author, count(m) AS count
        ORDER BY count DESC, author
        LIMIT 200
        \"\"\"
        with d.session() as sess:
            return [r.data() for r in sess.run(q)]

    @app.get("/similar/{model_id}")
    def similar(model_id: str):
        d = get_driver()
        q = \"\"\"
        MATCH (m:Model {id:$id})-[:HAS_TAG]->(t:Tag)<-[:HAS_TAG]-(other:Model)
        WHERE other.id <> m.id
        WITH other, count(t) AS shared
        RETURN other.id AS id, shared
        ORDER BY shared DESC, id
        LIMIT 25
        \"\"\"
        with d.session() as sess:
            return [r.data() for r in sess.run(q, {"id": model_id})]

    return app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host=os.getenv("API_HOST","0.0.0.0"), port=int(os.getenv("API_PORT","8091")))
""").strip(), encoding="utf-8")

# Zip it
zip_path = "/mnt/data/hf-apis.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for path in root.rglob("*"):
        if path.is_file():
            z.write(path, arcname=str(path.relative_to(root)))

zip_path
