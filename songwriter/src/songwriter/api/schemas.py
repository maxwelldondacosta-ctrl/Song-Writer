"""Pydantic v2 models. Cross-plan contract — shared with the Claude Code skill and the UI."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


LockState = Literal["draft", "edited", "locked"]
RuleResult = Literal["pass", "warn", "fail", "unrun"]


class IntentStory(BaseModel):
    event: str
    emotion: str
    resolution: str


class Intent(BaseModel):
    topic: str
    emotion_arc: str
    story: IntentStory


class Production(BaseModel):
    bpm: int = Field(..., ge=30, le=240)
    structure_template: str
    energy_curve: list[float] = Field(default_factory=list)


class SectionValidation(BaseModel):
    singability: RuleResult = "unrun"
    cadence: RuleResult = "unrun"
    phonetic_texture: RuleResult = "unrun"
    rhyme_cadence: RuleResult = "unrun"
    story_sentence: RuleResult = "unrun"
    warnings: list[str] = Field(default_factory=list)


class CohesionIssue(BaseModel):
    """One specific cross-section cohesion problem the LLM flagged."""
    section_ids: list[str] = Field(default_factory=list)
    note: str


class CohesionValidation(BaseModel):
    """Whole-song narrative-cohesion check (verses + chorus + bridge as one track)."""
    verdict: RuleResult = "unrun"
    summary: str = ""
    issues: list[CohesionIssue] = Field(default_factory=list)


class Section(BaseModel):
    id: str
    label: str
    lock_state: LockState
    lyrics: list[str] = Field(default_factory=list)
    cadence_pattern: str
    rhyme_scheme: str | None = None  # e.g. AABB, ABAB, ABCB, AAAA, free
    validation: SectionValidation = Field(default_factory=SectionValidation)
    phonetic_overlay: list[dict] = Field(default_factory=list)


class SunoPrompt(BaseModel):
    current: str = ""
    history: list[dict] = Field(default_factory=list)


class Request(BaseModel):
    type: Literal["suggest_alternatives", "tighten_cadence", "rewrite_section", "regen_descriptor"]
    section: str | None = None
    line: int | None = None
    count: int | None = None
    constraint: str | None = None
    payload: dict | None = None


class Song(BaseModel):
    id: str
    title: str
    created: datetime = Field(default_factory=datetime.utcnow)
    modified: datetime = Field(default_factory=datetime.utcnow)
    genre: str
    sub_genre: str
    songwriter_lens: str | None = None
    intent: Intent
    production: Production
    sections: list[Section] = Field(default_factory=list)
    suno_prompt: SunoPrompt = Field(default_factory=SunoPrompt)
    requests: list[Request] = Field(default_factory=list)
    notes: str = ""
    cohesion: CohesionValidation = Field(default_factory=CohesionValidation)
    last_modified_by: Literal["ui", "skill", "api"] = "api"
