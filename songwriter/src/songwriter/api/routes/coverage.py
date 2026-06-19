"""GET /songs/{slug}/coverage — pre-flight check of every DB lookup.

Tells the UI which seed-data tables will hit and which silently degrade.
Read-only, no LLM. The coverage strip in the editor renders this as a row
of green/amber/red chips so the user sees gaps *before* clicking Generate.

Items checked:
  - production_fingerprint (by sub_genre)
  - emotion_tempo_map (by emotion × sub_genre)
  - songwriter_lens (by slug)
  - cadence_patterns (per section's cadence slug)
  - anchor vocab (DB-only path of the resolver — no LLM call)
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from songwriter.api.deps import get_db, get_settings
from songwriter.api.settings import Settings
from songwriter.api.songs_io import path_for_slug, read_song
from songwriter.api.vocab_resolver import _exact, _sibling_genre, _sibling_emotion


router = APIRouter()


def _resolve_sub_genre_id(db: sqlite3.Connection, dotted: str) -> int | None:
    if "." in dotted:
        g_slug, sg_slug = dotted.split(".", 1)
        row = db.execute(
            """
            SELECT sg.id FROM sub_genres sg
            JOIN genres g ON g.id = sg.genre_id
            WHERE g.slug = ? AND sg.slug = ?
            """,
            (g_slug, sg_slug),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT id FROM sub_genres WHERE slug = ?", (dotted,)
        ).fetchone()
    return row["id"] if row else None


@router.get("/songs/{slug}/coverage")
def get_coverage(
    slug: str,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
) -> dict:
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song = read_song(settings.songs_dir, slug)

    sg_id = _resolve_sub_genre_id(db, song.sub_genre)

    # 1. Production fingerprint
    prod_row = None
    if sg_id is not None:
        prod_row = db.execute(
            "SELECT 1 FROM production_fingerprints WHERE sub_genre_id = ?", (sg_id,)
        ).fetchone()
    production_status = (
        "missing-subgenre" if sg_id is None
        else "ok" if prod_row else "missing"
    )

    # 2. Emotion-tempo
    emotion = song.intent.emotion_arc or ""
    if not emotion:
        emotion_status = "unset"
    elif sg_id is None:
        emotion_status = "missing-subgenre"
    else:
        et_row = db.execute(
            "SELECT 1 FROM emotion_tempo_map WHERE emotion = ? AND sub_genre_id = ?",
            (emotion, sg_id),
        ).fetchone()
        emotion_status = "ok" if et_row else "missing"

    # 3. Lens
    if not song.songwriter_lens:
        lens_status = "unset"
    else:
        lens_row = db.execute(
            "SELECT 1 FROM songwriter_profiles WHERE slug = ?", (song.songwriter_lens,)
        ).fetchone()
        lens_status = "ok" if lens_row else "missing"

    # 4. Cadence patterns per section
    cadence_per_section: list[dict] = []
    for s in song.sections:
        slug_ = s.cadence_pattern
        if not slug_:
            cadence_per_section.append({"section_id": s.id, "label": s.label, "cadence": None, "status": "unset"})
            continue
        row = db.execute(
            "SELECT 1 FROM cadence_patterns WHERE slug = ?", (slug_,)
        ).fetchone()
        cadence_per_section.append({
            "section_id": s.id, "label": s.label, "cadence": slug_,
            "status": "ok" if row else "missing",
        })
    cadence_status = (
        "ok" if cadence_per_section and all(c["status"] == "ok" for c in cadence_per_section)
        else "missing" if any(c["status"] == "missing" for c in cadence_per_section)
        else "partial" if cadence_per_section
        else "no-sections"
    )

    # 5. Anchor vocab (DB path only, never LLM here)
    anchor_source = "none"
    anchor_slug: str | None = None
    anchor_count = 0
    if song.genre and emotion:
        if (w := _exact(db, song.genre, emotion)):
            anchor_source, anchor_slug, anchor_count = "exact", f"{song.genre.lower()}.{emotion.lower()}", len(w)
        elif (sib := _sibling_genre(db, song.genre, emotion)):
            anchor_source, anchor_slug, anchor_count = "sibling-genre", sib[1], len(sib[0])
        elif (cross := _sibling_emotion(db, emotion)):
            anchor_source, anchor_slug, anchor_count = "sibling-emotion", cross[1], len(cross[0])

    # Roll-up: ready if every required item is ok or unset (unset is user choice, not a gap).
    items = {
        "production_fingerprint": production_status,
        "emotion_tempo": emotion_status,
        "songwriter_lens": lens_status,
        "cadence_patterns": cadence_status,
    }
    ready = all(v in ("ok", "unset", "no-sections") for v in items.values())

    return {
        "song_id": song.id,
        "ready": ready,
        "items": items,
        "cadence_per_section": cadence_per_section,
        "anchor_vocab": {
            "source": anchor_source,
            "bank_slug": anchor_slug,
            "count": anchor_count,
            "would_use_llm": anchor_source == "none" and bool(emotion),
        },
    }
