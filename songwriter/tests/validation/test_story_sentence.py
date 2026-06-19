from unittest.mock import patch

from songwriter.api.validation.story_sentence import check_section
from songwriter.api.validation import ValidationContext


def _ctx():
    return ValidationContext(cadence_pattern=None, emotion="surrender", sub_genre="pop.alt-pop")


def test_story_sentence_pass(monkeypatch):
    fake = {"verdict": "pass", "per_line": [{"line_index": 0, "verdict": "pass", "note": "ok"}]}
    with patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake):
        outcome = check_section(["a single line"], _ctx(), intent_story={"event":"e","emotion":"m","resolution":"r"})
    assert outcome.verdict == "pass"


def test_story_sentence_fail_aggregates_warnings():
    fake = {
        "verdict": "fail",
        "per_line": [
            {"line_index": 0, "verdict": "pass", "note": "ok"},
            {"line_index": 1, "verdict": "fail", "note": "breaks narrative continuity"},
        ],
    }
    with patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake):
        outcome = check_section(["a", "b"], _ctx(), intent_story={"event":"e","emotion":"m","resolution":"r"})
    assert outcome.verdict == "fail"
    assert any("continuity" in w for w in outcome.warnings)


def test_story_sentence_handles_llm_error(monkeypatch):
    from songwriter.api.llm import LLMError
    with patch("songwriter.api.validation.story_sentence.ask_claude_json", side_effect=LLMError("boom")):
        outcome = check_section(["a"], _ctx(), intent_story={"event":"e","emotion":"m","resolution":"r"})
    assert outcome.verdict == "warn"
    assert any("LLM" in w or "boom" in w for w in outcome.warnings)
