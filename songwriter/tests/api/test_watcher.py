import asyncio
import time
from pathlib import Path

import pytest

from songwriter.api.watcher import SongFileWatcher
from songwriter.api.ws import ConnectionManager


@pytest.mark.asyncio
async def test_watcher_broadcasts_on_external_write(tmp_path):
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    mgr = ConnectionManager()

    # capture broadcasts
    captured: list[tuple[str, dict]] = []
    async def fake_broadcast(slug, payload):
        captured.append((slug, payload))
    mgr.broadcast = fake_broadcast  # type: ignore

    watcher = SongFileWatcher(songs_dir=songs_dir, manager=mgr)
    watcher.start()
    try:
        # write a valid song JSON externally
        from songwriter.api.schemas import Song, Intent, IntentStory, Production
        song = Song(
            id="ext", title="E", genre="pop", sub_genre="alt-pop",
            intent=Intent(topic="t", emotion_arc="surrender",
                          story=IntentStory(event="e", emotion="m", resolution="r")),
            production=Production(bpm=88, structure_template="pop.standard", energy_curve=[0.4]),
        )
        (songs_dir / "ext.json").write_text(song.model_dump_json())
        # wait for watcher
        for _ in range(40):
            if captured: break
            await asyncio.sleep(0.05)
    finally:
        watcher.stop()

    assert captured, "expected at least one broadcast"
    slug, payload = captured[0]
    assert slug == "ext"
    assert payload["type"] == "update"
    assert payload.get("source") == "external"


def test_self_write_is_suppressed(tmp_path):
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    mgr = ConnectionManager()
    watcher = SongFileWatcher(songs_dir=songs_dir, manager=mgr)
    watcher.note_self_write("self")
    # within suppression window — not "external"
    assert watcher._is_self_write("self") is True
    # outside window
    watcher._self_writes["self"] = time.time() - 10
    assert watcher._is_self_write("self") is False
