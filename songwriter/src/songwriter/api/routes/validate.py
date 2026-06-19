import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from songwriter.api.deps import get_db, get_settings
from songwriter.api.schemas import Song
from songwriter.api.settings import Settings
from songwriter.api.songs_io import path_for_slug, read_song, write_song
from songwriter.api.validation.orchestrator import validate_song
from songwriter.api.ws import manager


router = APIRouter()


@router.post("/songs/{slug}/validate")
async def run_validate(
    slug: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    include_llm: bool = Query(True),
) -> Song:
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song = read_song(settings.songs_dir, slug)
    song = validate_song(song, db, include_llm=include_llm)
    song.last_modified_by = "api"
    song.modified = datetime.now(timezone.utc)
    watcher = getattr(request.app.state, "watcher", None)
    if watcher is not None:
        watcher.note_self_write(slug)
    write_song(settings.songs_dir, song)
    await manager.broadcast(slug, {"type": "update", "song": song.model_dump(mode="json")})
    return song
