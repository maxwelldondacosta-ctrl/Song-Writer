from unittest.mock import patch

from songwriter.api.schemas import Song, Intent, IntentStory, Production, Section, SectionValidation
from songwriter.api.validation.cohesion import check_song


def _song_with_sections(sections: list[Section]) -> Song:
    return Song(
        id="x", title="Test",
        genre="rnb", sub_genre="alt-rnb",
        intent=Intent(
            topic="late-night confession",
            emotion_arc="surrender",
            story=IntentStory(event="she calls late", emotion="I should know better", resolution="I let her in"),
        ),
        production=Production(bpm=72, structure_template="rnb.intimate-confession", energy_curve=[0.3, 0.5]),
        sections=sections,
    )


def _section(id: str, label: str, lyrics: list[str]) -> Section:
    return Section(
        id=id, label=label, lock_state="draft",
        cadence_pattern="melodic-glide", lyrics=lyrics,
    )


def test_cohesion_unrun_when_too_few_sections():
    song = _song_with_sections([_section("v1", "Verse 1", ["one drafted line"])])
    out = check_song(song)
    assert out.verdict == "unrun"
    assert "2+" in out.summary


def test_cohesion_unrun_when_no_lyrics():
    song = _song_with_sections([
        _section("v1", "Verse 1", ["", ""]),
        _section("ch", "Chorus", []),
    ])
    out = check_song(song)
    assert out.verdict == "unrun"


def test_cohesion_pass_no_issues():
    fake = {
        "verdict": "pass",
        "summary": "Sections cohere — porch image carries from verse to chorus.",
        "issues": [],
    }
    song = _song_with_sections([
        _section("v1", "Verse 1", ["she called me late", "the porch was warm"]),
        _section("ch", "Chorus", ["I let her in", "the porch was warm"]),
    ])
    with patch("songwriter.api.validation.cohesion.ask_claude_json", return_value=fake):
        out = check_song(song)
    assert out.verdict == "pass"
    assert "porch" in out.summary
    assert out.issues == []


def test_cohesion_warn_with_specific_issue():
    fake = {
        "verdict": "warn",
        "summary": "Pronoun shift between verses without a marker.",
        "issues": [
            {"section_ids": ["v1", "v2"], "note": "verse 1 is in 'I' but verse 2 switches to 'we' with no bridge to mark the shift"},
        ],
    }
    song = _song_with_sections([
        _section("v1", "Verse 1", ["I called her late"]),
        _section("v2", "Verse 2", ["we both knew it was wrong"]),
    ])
    with patch("songwriter.api.validation.cohesion.ask_claude_json", return_value=fake):
        out = check_song(song)
    assert out.verdict == "warn"
    assert len(out.issues) == 1
    assert "v1" in out.issues[0].section_ids
    assert "v2" in out.issues[0].section_ids


def test_cohesion_handles_llm_error():
    from songwriter.api.llm import LLMError
    song = _song_with_sections([
        _section("v1", "Verse 1", ["a line"]),
        _section("ch", "Chorus", ["another line"]),
    ])
    with patch("songwriter.api.validation.cohesion.ask_claude_json", side_effect=LLMError("boom")):
        out = check_song(song)
    assert out.verdict == "warn"
    assert "boom" in out.summary or "failed" in out.summary.lower()


def test_cohesion_handles_malformed_json():
    song = _song_with_sections([
        _section("v1", "Verse 1", ["line"]),
        _section("ch", "Chorus", ["line"]),
    ])
    with patch("songwriter.api.validation.cohesion.ask_claude_json", return_value="not a dict"):
        out = check_song(song)
    assert out.verdict == "warn"
    assert "malformed" in out.summary.lower()
