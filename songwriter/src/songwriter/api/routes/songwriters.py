import json
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db


router = APIRouter()


_JSON_COLS = ("sub_genres", "notable_credits", "craft_signature", "personality_traits",
              "writing_style", "preferred_cadences", "vocab_fingerprint",
              "phonetic_fingerprint", "structure_preferences", "reference_tracks")


def _hydrate(row: sqlite3.Row) -> dict:
    d = dict(row)
    for c in _JSON_COLS:
        d[c] = json.loads(d[c]) if d.get(c) else None
    return d


@router.get("/songwriter-profiles")
def list_profiles(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    genre: str | None = Query(None),
    role: str | None = Query(None),
):
    sql = """
        SELECT sp.*, g.slug AS primary_genre_slug
        FROM songwriter_profiles sp
        LEFT JOIN genres g ON g.id = sp.primary_genre_id
    """
    where = []
    args: list = []
    if genre:
        where.append("g.slug = ?")
        args.append(genre)
    if role:
        where.append("sp.role = ?")
        args.append(role)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY sp.display_name"
    rows = db.execute(sql, args).fetchall()
    return [_hydrate(r) for r in rows]


@router.get("/songwriter-profiles/{slug}")
def get_profile(slug: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    row = db.execute(
        """
        SELECT sp.*, g.slug AS primary_genre_slug
        FROM songwriter_profiles sp
        LEFT JOIN genres g ON g.id = sp.primary_genre_id
        WHERE sp.slug = ?
        """,
        (slug,),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"songwriter profile {slug!r} not found")
    return _hydrate(row)
