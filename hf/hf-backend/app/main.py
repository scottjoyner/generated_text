from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
from .db import SessionLocal, Base, engine
from .search import list_models, get_facets
from .models import Model
from .neo import driver

def create_app() -> FastAPI:
    app = FastAPI(title="HF Models Backend", version="0.1.0")

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
        with SessionLocal() as s:
            data = list_models(
                s,
                q=q,
                author=author,
                tags=tag,
                license=license,
                pipeline=pipeline,
                min_downloads=min_downloads,
                gated=gated,
                private=private,
                sort=sort,
                order=order,
                page=page,
                page_size=page_size,
            )
            return JSONResponse(data)

    @app.get("/models/{model_id}")
    def model_detail(model_id: str):
        with SessionLocal() as s:
            m = s.get(Model, model_id)
            if not m:
                return JSONResponse({"error": "not found"}, status_code=404)
            return {
                "id": m.id,
                "author": m.author.name if m.author else None,
                "name": m.name,
                "private": m.private,
                "gated": m.gated,
                "sha": m.sha,
                "pipeline_tag": m.pipeline_tag,
                "library_name": m.library_name,
                "license": m.license,
                "license_raw": m.license_raw,
                "downloads": m.downloads,
                "likes": m.likes,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "last_modified": m.last_modified.isoformat() if m.last_modified else None,
                "card_summary": m.card_summary,
                "tags": [mt.tag for mt in m.tags],
                "siblings": [s.rfilename for s in m.siblings],
                "spaces": [sp.space_name for sp in m.spaces],
                "raw": m.raw,
            }

    @app.get("/tags")
    def tags():
        with SessionLocal() as s:
            return JSONResponse(get_facets(s)["tags"])

    @app.get("/authors")
    def authors():
        with SessionLocal() as s:
            return JSONResponse(get_facets(s)["authors"])

    @app.get("/similar/{model_id}")
    def similar(model_id: str):
        # Graph-based: models sharing the most tags with the given model
        q = """        MATCH (m:Model {id:$id})-[:HAS_TAG]->(t:Tag)<-[:HAS_TAG]-(other:Model)
        WHERE other.id <> m.id
        WITH other, count(*) as shared
        RETURN other.id as id, shared
        ORDER BY shared DESC
        LIMIT 25
        """
        with driver.session() as sess:
            rows = list(sess.run(q, {"id": model_id}))
        return [{"id": r["id"], "shared_tags": r["shared"]} for r in rows]

    return app
