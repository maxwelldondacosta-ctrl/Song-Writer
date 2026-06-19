from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from songwriter.api.deps import get_settings
from songwriter.api.schemas import Song
from songwriter.api.settings import Settings
from songwriter.api.songs_io import list_song_slugs, path_for_slug, read_song, write_song
from songwriter.api.ws import manager


router = APIRouter()


@router.get("/songs")
def list_songs(settings: Annotated[Settings, Depends(get_settings)]) -> list[dict]:
    out = []
    for slug in list_song_slugs(settings.songs_dir):
        try:
            song = read_song(settings.songs_dir, slug)
        except Exception:
            continue
        out.append({
            "id": song.id, "title": song.title, "genre": song.genre,
            "sub_genre": song.sub_genre, "songwriter_lens": song.songwriter_lens,
            "modified": song.modified.isoformat(),
        })
    return out


@router.post("/songs", status_code=201)
async def create_song(
    song: Song,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Song:
    if path_for_slug(settings.songs_dir, song.id).exists():
        raise HTTPException(409, f"song {song.id!r} already exists")
    song.last_modified_by = "api"
    song.modified = datetime.now(timezone.utc)
    watcher = getattr(request.app.state, "watcher", None)
    if watcher is not None:
        watcher.note_self_write(song.id)
    write_song(settings.songs_dir, song)
    await manager.broadcast(song.id, {"type": "update", "song": song.model_dump(mode="json")})
    return song


@router.get("/songs/{slug}")
def get_song(slug: str, settings: Annotated[Settings, Depends(get_settings)]) -> Song:
    try:
        return read_song(settings.songs_dir, slug)
    except FileNotFoundError:
        raise HTTPException(404, f"song {slug!r} not found")


@router.put("/songs/{slug}")
async def update_song(
    slug: str,
    song: Song,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Song:
    if song.id != slug:
        raise HTTPException(400, "song.id does not match URL slug")
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song.last_modified_by = "api"
    song.modified = datetime.now(timezone.utc)
    watcher = getattr(request.app.state, "watcher", None)
    if watcher is not None:
        watcher.note_self_write(slug)
    write_song(settings.songs_dir, song)
    await manager.broadcast(slug, {"type": "update", "song": song.model_dump(mode="json")})
    return song


@router.websocket("/ws/songs/{slug}")
async def ws_song(websocket: WebSocket, slug: str):
    settings: Settings = websocket.app.state.settings
    await manager.connect(slug, websocket)
    try:
        try:
            snapshot = read_song(settings.songs_dir, slug)
            await websocket.send_json({"type": "snapshot", "song": snapshot.model_dump(mode="json")})
        except FileNotFoundError:
            await websocket.send_json({"type": "snapshot", "song": None})
        while True:
            await websocket.receive_text()  # keep-alive; clients can send pings
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(slug, websocket)
