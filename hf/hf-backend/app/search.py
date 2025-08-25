from typing import Optional, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, text
from .models import Model, Author, ModelTag

VALID_SORT = {
    "downloads": Model.downloads,
    "likes": Model.likes,
    "last_modified": Model.last_modified,
    "created_at": Model.created_at,
    "id": Model.id,
    "name": Model.name,
}

def list_models(
    session: Session,
    q: Optional[str] = None,
    author: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
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
    stmt = select(Model).join(Author, isouter=True)
    if tags:
        # Intersect all tags (AND). For OR, change to in_ and distinct.
        for t in tags:
            alias = ModelTag
            stmt = stmt.join(alias, (alias.model_id == Model.id) & (alias.tag == t))

    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(Model.id.ilike(like), Model.name.ilike(like), Model.card_summary.ilike(like)))
    if author:
        filters.append(Author.name == author)
    if license:
        filters.append(Model.license == license)
    if pipeline:
        filters.append(Model.pipeline_tag == pipeline)
    if min_downloads is not None:
        filters.append(Model.downloads >= min_downloads)
    if gated is not None:
        filters.append(Model.gated == gated)
    if private is not None:
        filters.append(Model.private == private)
    if filters:
        stmt = stmt.where(and_(*filters))

    # Sorting
    sort_col = VALID_SORT.get(sort, Model.downloads)
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_col.asc().nullslast())
    else:
        stmt = stmt.order_by(sort_col.desc().nullslast())

    # Pagination
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    offset = (max(1, page) - 1) * max(1, page_size)
    stmt = stmt.offset(offset).limit(page_size)
    rows = session.scalars(stmt).all()

    def to_dict(m: Model):
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
            "downloads": m.downloads,
            "likes": m.likes,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "last_modified": m.last_modified.isoformat() if m.last_modified else None,
            "tags": [mt.tag for mt in m.tags],
            "siblings": [s.rfilename for s in m.siblings],
            "spaces": [sp.space_name for sp in m.spaces],
        }

    return {
        "items": [to_dict(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "total": total or 0,
    }

def get_facets(session: Session):
    top_tags = session.execute(
        select(ModelTag.tag, func.count()).group_by(ModelTag.tag).order_by(func.count().desc()).limit(50)
    ).all()
    top_authors = session.execute(
        select(func.coalesce(Model.author_id, -1), func.count()).group_by(Model.author_id).order_by(func.count().desc()).limit(50)
    ).all()
    # Map author ids to names
    author_map = {a.id: a.name for a in session.scalars(select(Author)).all()}
    return {
        "tags": [{"tag": t, "count": c} for (t, c) in top_tags],
        "authors": [{"author": author_map.get(aid, None), "count": c} for (aid, c) in top_authors],
    }
