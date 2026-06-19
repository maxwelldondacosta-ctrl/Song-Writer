import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

from songwriter.api.schemas import Section, Song, SectionValidation
from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.tokenizer import tokenize_line
from songwriter.api.validation import singability, cadence, phonetic_texture, rhyme_cadence, story_sentence, cohesion


def _load_cadence(db: sqlite3.Connection, slug: str) -> CadencePattern | None:
    row = db.execute(
        "SELECT slug, syllable_template, stress_template, rhyme_compatibility FROM cadence_patterns WHERE slug = ?",
        (slug,),
    ).fetchone()
    if not row:
        return None
    return CadencePattern(
        slug=row["slug"],
        syllable_template=row["syllable_template"] or "?",
        stress_template=row["stress_template"] or "?",
        rhyme_compatibility=json.loads(row["rhyme_compatibility"]) if row["rhyme_compatibility"] else {},
    )


def _worst(verdicts: list[str]) -> str:
    rank = {"fail": 3, "warn": 2, "pass": 1, "unrun": 0}
    return max(verdicts, key=lambda v: rank.get(v, 0))


def validate_song(
    song: Song,
    db: sqlite3.Connection,
    *,
    include_llm: bool = True,
    llm_section_ids: set[str] | None = None,
) -> Song:
    """Validate all sections. LLM checks (story_sentence, cohesion) are expensive:
    - cohesion always runs once (it reads the whole song)
    - story_sentence runs only for sections in llm_section_ids (default: all sections)
      Use llm_section_ids=target_ids in the draft loop to avoid N × LLM calls.
    """
    if include_llm:
        song.cohesion = cohesion.check_song(song)

    # Run deterministic checks for all sections first (fast, in-process).
    intent_story = song.intent.story.model_dump()
    section_data: list[dict] = []
    for section in song.sections:
        cp = _load_cadence(db, section.cadence_pattern)
        ctx = ValidationContext(cadence_pattern=cp, emotion=song.intent.emotion_arc, sub_genre=song.sub_genre)
        line_tokens = [tokenize_line(line, db) for line in section.lyrics]

        per_line_singability = [
            singability.check_line(toks, ctx, raw_line=line)
            for toks, line in zip(line_tokens, section.lyrics)
        ]
        per_line_cadence = [cadence.check_line(toks, ctx) for toks in line_tokens]
        per_line_pt = [phonetic_texture.check_line(toks, ctx) for toks in line_tokens]
        rc_outcome = rhyme_cadence.check_section(line_tokens, ctx)

        warnings: list[str] = []
        for r in per_line_singability + per_line_cadence + per_line_pt + [rc_outcome]:
            warnings.extend(r.warnings)

        run_llm = include_llm and section.lyrics and (
            llm_section_ids is None or section.id in llm_section_ids
        )
        section_data.append({
            "section": section,
            "ctx": ctx,
            "per_line_singability": per_line_singability,
            "per_line_cadence": per_line_cadence,
            "per_line_pt": per_line_pt,
            "rc_outcome": rc_outcome,
            "warnings": warnings,
            "run_llm": run_llm,
        })

    # Fire all LLM story-sentence checks in parallel (each is an independent HTTP call).
    llm_sections = [d for d in section_data if d["run_llm"]]
    story_results: dict[str, tuple] = {}  # section.id → (verdict, warnings)
    if llm_sections:
        def _check(d: dict) -> tuple[str, tuple]:
            outcome = story_sentence.check_section(
                d["section"].lyrics, d["ctx"], intent_story=intent_story
            )
            return d["section"].id, (outcome.verdict, outcome.warnings)

        with ThreadPoolExecutor(max_workers=min(4, len(llm_sections))) as pool:
            for section_id, result in pool.map(lambda d: _check(d), llm_sections):
                story_results[section_id] = result

    # Apply results back to sections.
    for d in section_data:
        section = d["section"]
        warnings = d["warnings"]
        story = "unrun"
        if d["run_llm"] and section.id in story_results:
            verdict, story_warnings = story_results[section.id]
            story = verdict
            warnings.extend(story_warnings)

        section.validation = SectionValidation(
            singability=_worst([r.verdict for r in d["per_line_singability"]]) if d["per_line_singability"] else "unrun",
            cadence=_worst([r.verdict for r in d["per_line_cadence"]]) if d["per_line_cadence"] else "unrun",
            phonetic_texture=_worst([r.verdict for r in d["per_line_pt"]]) if d["per_line_pt"] else "unrun",
            rhyme_cadence=d["rc_outcome"].verdict,
            story_sentence=story,
            warnings=warnings,
        )
    return song
