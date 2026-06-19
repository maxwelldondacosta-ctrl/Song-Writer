import json
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db


router = APIRouter()


def _resolve_sub_genre_id(db: sqlite3.Connection, dotted: str) -> int | None:
    if "." in dotted:
        g_slug, sg_slug = dotted.split(".", 1)
        row = db.execute(
            """
            SELECT sg.id FROM sub_genres sg JOIN genres g ON g.id = sg.genre_id
            WHERE g.slug = ? AND sg.slug = ?
            """,
            (g_slug, sg_slug),
        ).fetchone()
    else:
        row = db.execute("SELECT id FROM sub_genres WHERE slug = ?", (dotted,)).fetchone()
    return row["id"] if row else None


_FP_JSON_COLS = ("instrumentation", "vocal_style", "mix_attributes",
                 "positive_descriptors", "negative_descriptors")


@router.get("/production-fingerprints/{sub_genre}")
def get_production_fingerprint(sub_genre: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    sg_id = _resolve_sub_genre_id(db, sub_genre)
    if sg_id is None:
        raise HTTPException(404, f"sub-genre {sub_genre!r} not found")
    row = db.execute(
        "SELECT * FROM production_fingerprints WHERE sub_genre_id = ?", (sg_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"no fingerprint for {sub_genre!r}")
    out = dict(row)
    for c in _FP_JSON_COLS:
        out[c] = json.loads(out[c]) if out.get(c) else None
    return out


@router.get("/emotion-tempo")
def get_emotion_tempo(
    emotion: str,
    sub_genre: str,
    db: Annotated[sqlite3.Connection, Depends(get_db)],
):
    sg_id = _resolve_sub_genre_id(db, sub_genre)
    if sg_id is None:
        raise HTTPException(404, f"sub-genre {sub_genre!r} not found")
    row = db.execute(
        "SELECT * FROM emotion_tempo_map WHERE emotion = ? AND sub_genre_id = ?",
        (emotion, sg_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"no emotion-tempo entry for {emotion!r} × {sub_genre!r}")
    out = dict(row)
    out["energy_curve"] = json.loads(out["energy_curve"]) if out["energy_curve"] else []
    out["anti_prompts"] = json.loads(out["anti_prompts"]) if out["anti_prompts"] else []
    return out


@router.get("/structure-templates")
def list_structure_templates(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM structure_templates ORDER BY slug").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["sections"] = json.loads(d["sections"]) if d["sections"] else []
        d["genre_compatibility"] = json.loads(d["genre_compatibility"]) if d["genre_compatibility"] else []
        out.append(d)
    return out
