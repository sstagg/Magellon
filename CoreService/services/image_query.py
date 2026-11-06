"""Listing a session's images: one level or all, filtered, searched, sorted and paged in SQL.

Raw SQL over ``image i``. ``access_clause``/``access_params`` come from
get_session_filter_clause (row-level security) and apply to the outer query.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.pydantic_models import ImageDto
from services.image_filter import (CHILDREN_COUNT, FIELDS, FilterGroup, _like, compile_filter, field_sql,
                                   order_by, resolution_sql)


def _dialect(db: Session) -> str:
    return db.get_bind().dialect.name


def _columns(dialect: str) -> str:
    return f"""
    i.oid, i.name, i.defocus, i.dose, i.magnification AS mag, i.pixel_size AS pixelSize,
    i.parent_id, i.binning_x, i.session_id, {resolution_sql(dialect)} AS ctf_resolution,
    {CHILDREN_COUNT} AS children_count"""

# How many distinct values a field may have for the dialog to list them all.
LISTED_VALUES = 6


def image_dto(row) -> dict:
    return ImageDto(
        oid=row.oid,
        name=row.name,
        defocus=round(float(row.defocus) * 1.e6, 2) if row.defocus is not None else None,
        dose=row.dose,
        mag=row.mag,
        pixelSize=round(float(row.pixelSize) * row.binning_x * 1.e10, 3)
        if row.pixelSize is not None and row.binning_x is not None else None,
        parent_id=row.parent_id,
        session_id=row.session_id,
        children_count=row.children_count,
        resolution=round(float(row.ctf_resolution), 2) if row.ctf_resolution is not None else None,
    ).dict()


def _selection(session_id: bytes, access_clause: str, access_params: dict, *, parent_id: Optional[bytes],
               all_levels: bool, image_filter: Optional[FilterGroup], include_ancestors: bool,
               search: Optional[str], dialect: str):
    """(WITH clause, WHERE clause, parameters) choosing the images."""
    params = {"sessionId": session_id, **access_params}
    where = ["i.session_id = :sessionId"]
    if not all_levels:
        if parent_id is None:
            where.append("i.parent_id IS NULL")
        else:
            where.append("i.parent_id = :parentId")
            params["parentId"] = parent_id
    if search and search.strip():
        where.append("LOWER(i.name) LIKE :search ESCAPE '!'")
        params["search"] = f"%{_like(search.strip().lower())}%"
    cte = ""
    compiled = compile_filter(image_filter, dialect)
    if compiled:
        condition, filter_params = compiled
        params.update(filter_params)
        if include_ancestors:
            # The matches and every image above them, so they can be reached.
            cte = f"""WITH RECURSIVE shown (oid, parent_id) AS (
                SELECT i.oid, i.parent_id FROM image i WHERE i.session_id = :sessionId AND {condition}
                UNION
                SELECT p.oid, p.parent_id FROM image p JOIN shown s ON p.oid = s.parent_id
            ) """
            where.append("i.oid IN (SELECT oid FROM shown)")
        else:
            where.append(condition)
    return cte, " AND ".join(where) + " " + access_clause, params


def list_images(db: Session, session_id: bytes, access_clause: str, access_params: dict, *,
                parent_id: Optional[bytes] = None, all_levels: bool = False,
                image_filter: Optional[FilterGroup] = None, include_ancestors: bool = False,
                search: Optional[str] = None, sort: str = "related", descending: bool = False,
                page: int = 1, page_size: int = 50) -> dict:
    dialect = _dialect(db)
    cte, where, params = _selection(session_id, access_clause, access_params, parent_id=parent_id,
                                    all_levels=all_levels, image_filter=image_filter,
                                    include_ancestors=include_ancestors, search=search, dialect=dialect)
    total = db.execute(text(f"{cte}SELECT COUNT(*) FROM image i WHERE {where}"), params).scalar()
    rows = db.execute(text(
        f"{cte}SELECT {_columns(dialect)} FROM image i WHERE {where} "
        f"ORDER BY {order_by(sort, descending, all_levels, dialect)} LIMIT :limit OFFSET :offset"),
        {**params, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()
    return {
        "total_count": total,
        "page": page,
        "pageSize": page_size,
        "next_page": page + 1 if total > page * page_size else None,
        "result": [image_dto(row) for row in rows],
    }


def filter_summary(db: Session, session_id: bytes, access_clause: str, access_params: dict,
                   image_filter: Optional[FilterGroup]) -> dict:
    """How many of the session's images match, and what values each number field has."""
    dialect = _dialect(db)
    _, where, params = _selection(session_id, access_clause, access_params, parent_id=None, all_levels=True,
                                  image_filter=None, include_ancestors=False, search=None, dialect=dialect)
    numeric = [(field, field_sql(field, dialect)) for field, (_, is_number) in FIELDS.items() if is_number]
    stats = db.execute(text(
        "SELECT COUNT(*) AS total, " + ", ".join(
            f"MIN({expr}) AS {f}_min, MAX({expr}) AS {f}_max, COUNT({expr}) AS {f}_count, "
            f"COUNT(DISTINCT {expr}) AS {f}_distinct" for f, expr in numeric)
        + f" FROM image i WHERE {where}"), params).mappings().one()
    fields = {}
    for field, expr in numeric:
        count = stats[f"{field}_count"]
        info = {"count": count, "min": None, "max": None, "values": None}
        if count:
            info["min"] = float(stats[f"{field}_min"])
            info["max"] = float(stats[f"{field}_max"])
            if stats[f"{field}_distinct"] <= LISTED_VALUES:
                info["values"] = [float(v) for (v,) in db.execute(text(
                    f"SELECT DISTINCT {expr} AS v FROM image i WHERE {where} AND {expr} IS NOT NULL ORDER BY v"),
                    params).fetchall()]
        fields[field] = info

    matching = stats["total"]
    if compile_filter(image_filter, dialect):
        cte, filtered, filter_params = _selection(session_id, access_clause, access_params, parent_id=None,
                                                  all_levels=True, image_filter=image_filter,
                                                  include_ancestors=False, search=None, dialect=dialect)
        matching = db.execute(text(f"{cte}SELECT COUNT(*) FROM image i WHERE {filtered}"), filter_params).scalar()
    return {"total": stats["total"], "matching": matching, "fields": fields}


def image_path(db: Session, image_id: bytes) -> List[dict]:
    """The image and every image above it, top level first."""
    rows = db.execute(text(f"""
        WITH RECURSIVE path (oid, parent_id, depth) AS (
            SELECT oid, parent_id, 0 FROM image WHERE oid = :oid
            UNION ALL
            SELECT p.oid, p.parent_id, path.depth + 1 FROM image p JOIN path ON p.oid = path.parent_id
            WHERE path.depth < 20
        )
        SELECT {_columns(_dialect(db))} FROM image i JOIN path ON i.oid = path.oid ORDER BY path.depth DESC"""),
        {"oid": image_id}).fetchall()
    return [image_dto(row) for row in rows]
