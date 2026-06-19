import os
from pathlib import Path

from songwriter.api.schemas import Song


def path_for_slug(songs_dir: Path, slug: str) -> Path:
    return songs_dir / f"{slug}.json"


def read_song(songs_dir: Path, slug: str) -> Song:
    p = path_for_slug(songs_dir, slug)
    if not p.exists():
        raise FileNotFoundError(slug)
    return Song.model_validate_json(p.read_text())


def write_song(songs_dir: Path, song: Song) -> Path:
    songs_dir.mkdir(parents=True, exist_ok=True)
    target = path_for_slug(songs_dir, song.id)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(song.model_dump_json(indent=2))
    os.replace(tmp, target)
    return target


def list_song_slugs(songs_dir: Path) -> list[str]:
    if not songs_dir.exists():
        return []
    return sorted(p.stem for p in songs_dir.glob("*.json"))
