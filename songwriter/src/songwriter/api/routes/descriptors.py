import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from songwriter.api.deps import get_db
from songwriter.api.llm import ask_claude_json


router = APIRouter()


_HONORIFICS = re.compile(r"\b(mr|mrs|ms|the|dj)\b\.?", re.IGNORECASE)


def _normalize(name: str) -> str:
    s = _HONORIFICS.sub("", name).strip().lower()
    s = re.sub(r"[-_]", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _scrub(text: str, burn_words: list[str]) -> str:
    out = text
    for w in burn_words:
        out = re.sub(rf"\b{re.escape(w)}\b", "[scrubbed]", out, flags=re.IGNORECASE)
    return out


_GEN_PROMPT_TEMPLATE = """\
Describe the artist '{name}' for use in a music-generation prompt. Output STRICT JSON only.
Required keys: descriptor_short (≤30 words), descriptor_long (~80-120 words),
vocal_attributes (object), production_attrs (object), genre_context (string).
Constraints:
- The artist's name must NOT appear inside descriptor_short or descriptor_long.
- Describe vocal timbre, register, attack profile.
- Describe production: instrumentation, mix character, tempo zone.
- Avoid overused AI words like neon, chrome, ghost, midnight, shadow, silver.
- No song titles, no copyrighted lyric content.
Output the JSON inside a ```json fenced block.
"""


def _hydrate(row: sqlite3.Row) -> dict:
    d = dict(row)
    for c in ("vocal_attributes", "production_attrs"):
        d[c] = json.loads(d[c]) if d.get(c) else None
    return d


@router.get("/descriptors")
def list_descriptors(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    quality: str | None = Query(None, description="Filter by quality_state (unverified|reviewed|pinned)"),
    source: str | None = Query(None, description="Filter by source"),
):
    sql = "SELECT * FROM artist_descriptor_cache"
    where: list[str] = []
    args: list = []
    if quality:
        where.append("quality_state = ?"); args.append(quality)
    if source:
        where.append("source = ?"); args.append(source)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY use_count DESC, canonical_name"
    rows = db.execute(sql, args).fetchall()
    return [_hydrate(r) for r in rows]


@router.post("/descriptors/{name}/pin")
def pin_descriptor(name: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    normalized = _normalize(name)
    cur = db.execute(
        "UPDATE artist_descriptor_cache SET quality_state = 'pinned' WHERE normalized_name = ?",
        (normalized,),
    )
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, f"descriptor {name!r} not in cache")
    row = db.execute(
        "SELECT * FROM artist_descriptor_cache WHERE normalized_name = ?", (normalized,)
    ).fetchone()
    return _hydrate(row)


@router.post("/descriptors/{name}/unpin")
def unpin_descriptor(name: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    normalized = _normalize(name)
    cur = db.execute(
        "UPDATE artist_descriptor_cache SET quality_state = 'reviewed' WHERE normalized_name = ?",
        (normalized,),
    )
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, f"descriptor {name!r} not in cache")
    row = db.execute(
        "SELECT * FROM artist_descriptor_cache WHERE normalized_name = ?", (normalized,)
    ).fetchone()
    return _hydrate(row)


@router.delete("/descriptors/{name}")
def delete_descriptor(name: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    """Remove from cache. Useful before regen via subsequent GET."""
    normalized = _normalize(name)
    cur = db.execute(
        "DELETE FROM artist_descriptor_cache WHERE normalized_name = ?", (normalized,)
    )
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, f"descriptor {name!r} not in cache")
    return {"deleted": normalized}


@router.get("/descriptors/{name}")
def get_descriptor(name: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    normalized = _normalize(name)
    if not normalized:
        raise HTTPException(400, "empty name")

    row = db.execute(
        "SELECT * FROM artist_descriptor_cache WHERE normalized_name = ?", (normalized,)
    ).fetchone()
    if row is not None:
        db.execute(
            """
            UPDATE artist_descriptor_cache
            SET use_count = use_count + 1, last_used_at = ?
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), row["id"]),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM artist_descriptor_cache WHERE id = ?", (row["id"],)
        ).fetchone()
        return _hydrate(row)

    # MISS — generate via LLM
    payload = ask_claude_json(_GEN_PROMPT_TEMPLATE.format(name=name))
    if not isinstance(payload, dict) or "descriptor_short" not in payload:
        raise HTTPException(502, "LLM returned malformed descriptor")

    burn_rows = db.execute("SELECT word FROM suno_burn_list").fetchall()
    burn_words = [r["word"] for r in burn_rows]
    descriptor_short = _scrub(payload["descriptor_short"], burn_words)
    descriptor_long = _scrub(payload["descriptor_long"], burn_words)

    db.execute(
        """
        INSERT INTO artist_descriptor_cache
          (normalized_name, canonical_name, descriptor, descriptor_short, descriptor_long,
           vocal_attributes, production_attrs, genre_context,
           source, quality_state, use_count, last_used_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,1,?)
        """,
        (
            normalized, name, descriptor_short, descriptor_short, descriptor_long,
            json.dumps(payload.get("vocal_attributes") or {}),
            json.dumps(payload.get("production_attrs") or {}),
            payload.get("genre_context"),
            "auto-llm", "unverified",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()
    row = db.execute(
        "SELECT * FROM artist_descriptor_cache WHERE normalized_name = ?", (normalized,)
    ).fetchone()
    return _hydrate(row)
