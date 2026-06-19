import json
from pathlib import Path

import pytest

from songwriter.api.songs_io import path_for_slug, read_song, write_song, list_song_slugs
from songwriter.api.schemas import Song, Intent, IntentStory, Production


def _sample_song(slug="x") -> Song:
    return Song(
        id=slug, title="Sample", genre="pop", sub_genre="alt-pop",
        intent=Intent(topic="t", emotion_arc="surrender",
                      story=IntentStory(event="e", emotion="m", resolution="r")),
        production=Production(bpm=88, structure_template="pop.standard", energy_curve=[0.4]),
    )


def test_path_for_slug(tmp_path):
    p = path_for_slug(tmp_path, "abc")
    assert p == tmp_path / "abc.json"


def test_write_and_read_round_trip(tmp_path):
    s = _sample_song("trip")
    write_song(tmp_path, s)
    s2 = read_song(tmp_path, "trip")
    assert s2.title == "Sample"


def test_write_is_atomic(tmp_path):
    s = _sample_song("atomic")
    write_song(tmp_path, s)
    # crash sim: temp file should be gone after successful write
    assert not list(tmp_path.glob("*.tmp"))


def test_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_song(tmp_path, "ghost")


def test_list_song_slugs(tmp_path):
    write_song(tmp_path, _sample_song("a"))
    write_song(tmp_path, _sample_song("b"))
    (tmp_path / "ignore.txt").write_text("nope")
    assert sorted(list_song_slugs(tmp_path)) == ["a", "b"]
