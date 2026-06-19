import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / ".claude" / "skills" / "songwriting"
COMMAND_FILE = REPO / ".claude" / "commands" / "song.md"


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def test_song_command_exists_with_frontmatter():
    assert COMMAND_FILE.exists()
    fm = _frontmatter(COMMAND_FILE.read_text())
    assert fm.get("name") in ("song", "/song")
    assert "description" in fm


def test_song_command_dispatches_subcommands():
    text = COMMAND_FILE.read_text()
    # the command body must reference $ARGUMENTS so subcommands are routed
    assert "$ARGUMENTS" in text or "{{args}}" in text or "ARGUMENTS" in text
    for sub in ["new", "open", "draft", "refine", "alt", "validate", "lens", "prompt", "export", "list"]:
        assert sub in text, f"command should reference subcommand {sub!r}"


def test_skill_md_exists_with_frontmatter():
    skill_md = SKILL_DIR / "SKILL.md"
    assert skill_md.exists()
    fm = _frontmatter(skill_md.read_text())
    assert fm.get("name") == "songwriting"
    assert "description" in fm
    assert len(fm["description"]) > 30


def test_skill_references_api_base_url():
    body = (SKILL_DIR / "SKILL.md").read_text()
    assert "localhost:8000" in body, "skill should reference the API base URL"


def test_skill_lists_all_subcommands():
    body = (SKILL_DIR / "SKILL.md").read_text().lower()
    for sub in ["new", "open", "draft", "refine", "alt", "validate", "lens", "prompt", "export", "list"]:
        assert sub in body


def test_workflow_doc_exists_with_seven_steps():
    p = SKILL_DIR / "reference" / "workflow.md"
    assert p.exists()
    body = p.read_text()
    expected_steps = [
        "Story Rule",
        "Sentence Rule",
        "Phonetic Texture",
        "Cadence",
        "Genre Pattern",
        "Final Validation",
        "Suno Prompt",
    ]
    for step in expected_steps:
        assert step in body, f"workflow doc should reference step: {step}"


def test_workflow_doc_includes_wizard_for_new_command():
    body = (SKILL_DIR / "reference" / "workflow.md").read_text().lower()
    assert "wizard" in body or "6-step" in body or "6 steps" in body
    for term in ["genre", "sub-genre", "topic", "emotion", "lens"]:
        assert term in body


def test_lens_application_doc_loads_adoption_prompt():
    p = SKILL_DIR / "reference" / "lens-application.md"
    assert p.exists()
    body = p.read_text()
    assert "adoption_prompt" in body
    assert "songwriter-profiles" in body
    for role in ["pure-songwriter", "producer-songwriter", "singer-songwriter", "self-writing-artist"]:
        assert role in body


def test_descriptor_cache_doc_explains_pipeline():
    p = SKILL_DIR / "reference" / "descriptor-cache.md"
    assert p.exists()
    body = p.read_text().lower()
    assert "/descriptors/" in body
    assert "auto-llm" in body or "auto llm" in body
    assert "burn list" in body or "burn-list" in body or "scrub" in body
    assert "never" in body and ("name" in body or "artist" in body)


def test_prompt_refinement_doc_has_5_phases():
    p = SKILL_DIR / "reference" / "prompt-refinement.md"
    assert p.exists()
    body = p.read_text().lower()
    for phase in ["phase 1", "phase 2", "phase 3", "phase 4", "phase 5"]:
        assert phase in body
    assert "burn list" in body or "burn-list" in body or "scrub" in body
    assert "anti-prompt" in body or "anti prompt" in body or "negative" in body
    # standalone improve mode
    assert "--improve" in body or "improve" in body
