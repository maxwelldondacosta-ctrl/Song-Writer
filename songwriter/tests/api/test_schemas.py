import pytest
from pydantic import ValidationError

from songwriter.api.schemas import (
    Song, Section, SectionValidation, Intent, Production, IntentStory,
    Request as SongRequest, SunoPrompt,
)


def test_minimal_song_validates():
    s = Song(
        id="2026-04-30-test",
        title="Test",
        genre="pop",
        sub_genre="dance-pop",
        intent=Intent(topic="test", emotion_arc="defiance",
                      story=IntentStory(event="x", emotion="y", resolution="z")),
        production=Production(bpm=120, structure_template="pop.standard", energy_curve=[0.5]),
        sections=[],
    )
    assert s.id == "2026-04-30-test"


def test_section_with_validation_results():
    sec = Section(
        id="v1",
        label="Verse 1",
        lock_state="draft",
        lyrics=["a", "b"],
        cadence_pattern="melodic-glide",
        validation=SectionValidation(
            singability="pass",
            cadence="warn",
            phonetic_texture="pass",
            rhyme_cadence="pass",
            story_sentence="unrun",
            warnings=["second line fails singability cadence alignment"],
        ),
    )
    assert sec.validation.cadence == "warn"


def test_invalid_lock_state_raises():
    with pytest.raises(ValidationError):
        Section(id="v1", label="Verse 1", lock_state="superlocked",
                lyrics=[], cadence_pattern="pop-hook")


def test_song_round_trips_through_json(tmp_path):
    s = Song(
        id="x", title="X", genre="pop", sub_genre="alt-pop",
        intent=Intent(topic="t", emotion_arc="surrender",
                      story=IntentStory(event="e", emotion="m", resolution="r")),
        production=Production(bpm=88, structure_template="pop.standard", energy_curve=[0.4]),
        sections=[Section(id="v1", label="Verse 1", lock_state="draft",
                          lyrics=["one"], cadence_pattern="melodic-glide")],
    )
    p = tmp_path / "x.json"
    p.write_text(s.model_dump_json(indent=2))
    s2 = Song.model_validate_json(p.read_text())
    assert s2 == s


def test_request_entry_shape():
    r = SongRequest(type="suggest_alternatives", section="v1", line=2, count=3, constraint="more vulnerable")
    assert r.line == 2
