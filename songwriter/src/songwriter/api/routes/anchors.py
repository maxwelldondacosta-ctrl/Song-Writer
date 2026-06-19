"""GET /songs/{slug}/anchor-preview — show what vocab anchors a draft would use.

Pure read-only call into the resolver. Returns the same `(words, source, bank_slug)`
that `draft.py` and `alternatives.py` rely on, so the UI can preview the
anchoring *before* hitting Generate. Kills the "wait like a lemon" feedback —
user sees `source: llm-fallback` or `⚠ no anchors` up-front.

Defaults to `?include_llm=false` so opening the panel never burns an LLM call.
The user opts in with `?include_llm=true` to force the LLM-fallback step.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db, get_settings
from songwriter.api.settings import Settings
from songwriter.api.songs_io import path_for_slug, read_song
from songwriter.api.vocab_resolver import resolve_vocab


router = APIRouter()


@router.get("/songs/{slug}/anchor-preview")
def anchor_preview(
    slug: str,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    include_llm: bool = Query(
        False,
        description="If false (default), skip LLM fallback — no billed call. "
                    "Returns source='none' if no DB bank matches.",
    ),
) -> dict:
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song = read_song(settings.songs_dir, slug)

    lens_slug = song.songwriter_lens or ""

    if include_llm:
        words, source, bank_slug = resolve_vocab(
            db,
            genre=song.genre,
            emotion=song.intent.emotion_arc or "",
            topic=song.intent.topic or "",
            lens_slug=lens_slug,
        )
    else:
        # DB-only path: monkey-skip the LLM fallback by short-circuiting if
        # we'd hit it. Cleanest way is to call the same helpers directly.
        from songwriter.api.vocab_resolver import _exact, _sibling_genre, _sibling_emotion, _artist_corpus

        genre = song.genre
        emotion = song.intent.emotion_arc or ""
        words: list[str] = []
        source: str = "none"
        bank_slug: str | None = None

        if genre and emotion:
            if (w := _exact(db, genre, emotion)):
                words, source, bank_slug = w, "exact", f"{genre.lower()}.{emotion.lower()}"
            elif (sib := _sibling_genre(db, genre, emotion)):
                words, source, bank_slug = sib[0], "sibling-genre", sib[1]
            elif (cross := _sibling_emotion(db, emotion)):
                words, source, bank_slug = cross[0], "sibling-emotion", cross[1]
            elif lens_slug and (ac := _artist_corpus(db, lens_slug)):
                words, source, bank_slug = ac, "artist-corpus", f"{lens_slug}.corpus"

    return {
        "song_id": song.id,
        "genre": song.genre,
        "emotion": song.intent.emotion_arc or "",
        "topic": song.intent.topic or "",
        "source": source,
        "bank_slug": bank_slug,
        "count": len(words),
        "words": words,
        "include_llm": include_llm,
    }
