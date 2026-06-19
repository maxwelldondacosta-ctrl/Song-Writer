"""POST /songs/{slug}/draft — generate lyrics then repair only what fails.

Loop:
  1. Generate all target sections in one call (DRAFT task → Cerebras, max 1800 tokens out).
  2. Run deterministic validation (syllable, rhyme, phonetic).
  3. If anything fails: send ONLY the failing sections back for targeted repair
     (REPAIR task → Cerebras, max 500 tokens out). Apply only what changed.
  4. Repeat up to max_attempts. Keep the best scoring candidate.
  5. Final pass: LLM story + cohesion check on winner only.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db, get_settings
from songwriter.api.llm import LLMError, ask_llm_json as ask_claude_json
from songwriter.api.routes.draft_defaults import sections_for_genre
from songwriter.api.schemas import Section, Song
from songwriter.api.settings import Settings
from songwriter.api.songs_io import path_for_slug, read_song, write_song
from songwriter.api.validation.orchestrator import validate_song
from songwriter.api.vocab_resolver import resolve_vocab
from songwriter.api.ws import manager as ws_manager


router = APIRouter()

MAX_ATTEMPTS = 2


# ── Prompts ───────────────────────────────────────────────────────────────────

_INITIAL_PROMPT = """\
=== SONG WORLD ===
{world_block}

=== CRITICAL INSTRUCTION ===
The genre ({genre}/{sub_genre}) defines the BEAT AND RHYTHM only.
The world above defines ALL imagery — every noun, setting, character, and metaphor.
A fantasy RPG world → swords, maps, dungeons, ruins. NOT amps, basements, or tour vans.
A house party world → red cups, bass, kitchen tiles. NOT swords or ruins.
Write the world's images to a {genre} rhythm. Never the other way around.

=== SECTIONS TO WRITE ===
{section_block}
{lens_brief}{genre_craft}

SYLLABLE TARGETS — every line must hit these or the song won't sing:
{cadence_compact}

VOCABULARY — draw from these where natural (genre + emotion tuned):
{anchor_words}

RULES:
1. WORLD FIRST. If a noun doesn't exist in the world described above, cut it.
2. SYLLABLES. Every line within ±2 of target. Count contractions as 1 syllable.
3. CONCRETE. Name the object or action. Abstract words only in the hook payoff line.
4. SPECIFIC. If this line could appear in any other {genre} song, rewrite it.
5. RHYME. Pick the rhyme word FIRST, then write the line around it — never the reverse.
   - Acceptable: near-rhymes that share the stressed vowel sound (clear/here, down/crown).
   - Not acceptable: words that merely look similar (sealed/still, through/true — different vowels).
   - If you can't find a real rhyme, rewrite BOTH lines so they rhyme with each other.
   - Never leave a line unrhymed when the scheme requires it.
6. AVOID: {burn_words}

Output JSON in a ```json fenced block — nothing else:
{{"sections":[{{"id":"<id>","lyrics":["line","line",...]}}]}}
"""

_REPAIR_PROMPT = """\
=== SONG WORLD ===
{world_block}

Fix ONLY the failing sections below. Stay inside this world — every rewritten line must use imagery from it.
Genre ({genre}/{sub_genre}) = rhythm only. Do NOT introduce generic genre tropes.{lens_brief}{genre_craft}

SYLLABLE TARGETS:
{cadence_compact}

FAILING SECTIONS:
{failing_block}

HOW TO FIX:
- singability: wrong syllable count — recount in natural speech, rewrite to hit target ±2.
- rhyme_cadence: end word doesn't rhyme — pick the correct rhyme word first, then
  rewrite both lines of the pair so they flow naturally to that rhyme. Don't just
  swap the last word if the line doesn't make sense built around it.
- phonetic_texture: too many consonant clusters — use open vowels (ah, oh, ay).
- story_sentence: too abstract — replace with one concrete image from this world.

AVOID: {burn_words}

Return ONLY the sections you changed. Omit sections that are already good.
Output JSON in a ```json fenced block:
{{"sections":[{{"id":"<id>","lyrics":["line","line",...]}}]}}
"""


# ── World block ───────────────────────────────────────────────────────────────

def _world_block(song: Song) -> str:
    """Lead with the song's world so the model anchors to it before anything else.

    When the user has filled in story arc fields, use them directly.
    When they're empty, convert the topic into a concrete dramatic moment so the
    model has something to dramatise rather than just describe.
    """
    parts: list[str] = []
    if song.title:
        parts.append(f"Title: {song.title}")
    topic = (song.intent.topic or "").strip()
    if topic:
        parts.append(f"Theme: {topic}")
    s = song.intent.story
    arc_parts = [x.strip() for x in [s.event, s.emotion, s.resolution] if (x or "").strip()]
    if arc_parts:
        parts.append(f"Story arc: {' → '.join(arc_parts)}")
    else:
        # No arc supplied — ask the model to invent a specific scene from the theme.
        # "Write about X" produces generic lists. "Dramatise a moment where X" produces story.
        parts.append(
            "Story arc: (not provided — YOU must invent one specific dramatic moment "
            "that embodies this theme. Pick a real-feeling scene: a phone call, a room, "
            "a choice, a person. Ground every line in that moment.)"
        )
    if song.intent.emotion_arc:
        parts.append(f"Tone/mood: {song.intent.emotion_arc}")
    return "\n".join(parts) if parts else "(no brief provided — use the genre defaults)"


# ── Genre craft hints ─────────────────────────────────────────────────────────

_GENRE_CRAFT: dict[str, str] = {
    "rap": (
        "RAP CRAFT:\n"
        "- Each verse = ONE specific scene (a room, a time, a choice, a person). "
        "Not a list of things you do.\n"
        "- Show contrast through action: 'She called, I let it ring, wire hit at 9' "
        "— not 'I chose money over her'.\n"
        "- Use domain vocabulary as emotional metaphor: depreciation, leverage, "
        "compound interest, deed, wire, lease.\n"
        "- Rhyme quality: multi-syllable rhymes ('balance sheet / manage these') beat "
        "single-word rhymes every time. Aim for at least one multi per verse.\n"
        "- Internal rhymes on stressed syllables inside the line give rap its pocket — use them.\n"
        "- Every chorus line must be a standalone statement people will repeat.\n"
        "- Choose the rhyme word FIRST. If 'delete' is your end-word, build backward "
        "from there — don't write a line and hope something rhymes."
    ),
    "pop": (
        "POP CRAFT:\n"
        "- Hook must be a single image or feeling anyone can immediately feel.\n"
        "- Verses build toward the chorus reveal — don't give away the emotion early.\n"
        "- Use second-person ('you') or first-person ('I') — avoid 'one' or passive voice.\n"
        "- The bridge should shift perspective or time, not repeat the chorus idea."
    ),
    "rock": (
        "ROCK CRAFT:\n"
        "- Verses are cinematic — place the listener in a specific physical location.\n"
        "- Chorus is the emotional release, not a summary of the verse.\n"
        "- Use active verbs. Passive constructions kill rock energy.\n"
        "- Bridge should feel like a confession or a turn."
    ),
    "country": (
        "COUNTRY CRAFT:\n"
        "- Stories need a specific place (town, road, bar, kitchen) and a named feeling.\n"
        "- Rhyme naturally — forced rhymes stand out more in country than any other genre.\n"
        "- The detail that makes it personal is the detail that makes it universal.\n"
        "- End the song with a line that lands like a period, not a comma."
    ),
}


def _genre_craft_hint(genre: str, sub_genre: str) -> str:
    key = genre.lower()
    # Sub-genre overrides if we have it, otherwise fall back to genre
    for k in (sub_genre.lower(), key):
        if k in _GENRE_CRAFT:
            return "\n" + _GENRE_CRAFT[k]
    return ""


def _topic_short(song: Song) -> str:
    topic = (song.intent.topic or "").strip()
    return topic[:60] if topic else "this topic"


# ── Lean lens block ───────────────────────────────────────────────────────────

def _load_lens_brief(db: sqlite3.Connection, slug: str | None) -> str:
    """Compact lens: display name + adoption prompt (first paragraph only) + top 2 craft mechanics.
    ~80 tokens vs 294 tokens for the full block — saves ~200 tokens per call.
    """
    if not slug:
        return ""
    row = db.execute(
        "SELECT display_name, adoption_prompt, craft_signature FROM songwriter_profiles WHERE slug = ?",
        (slug,),
    ).fetchone()
    if not row:
        return ""
    parts = [f"LENS: {row['display_name']}"]
    ap = (row["adoption_prompt"] or "").strip()
    if ap:
        first_para = ap.split("\n")[0].strip()
        if first_para:
            parts.append(first_para)
    cs = json.loads(row["craft_signature"]) if row["craft_signature"] else []
    if cs:
        parts.append("KEY: " + "; ".join(cs[:2]))
    return "\n".join(parts)


# ── DB loaders ────────────────────────────────────────────────────────────────

def _load_burn_dict(db: sqlite3.Connection) -> dict[str, list[str]]:
    rows = db.execute(
        "SELECT word, alternatives FROM suno_burn_list WHERE severity IN ('strong', 'extreme')"
    ).fetchall()
    out: dict[str, list[str]] = {}
    for r in rows:
        try:
            out[r["word"]] = json.loads(r["alternatives"]) if r["alternatives"] else []
        except json.JSONDecodeError:
            out[r["word"]] = []
    return out


def _load_cadence_compact(db: sqlite3.Connection, sections: list[Section]) -> str:
    slugs = sorted({s.cadence_pattern for s in sections if s.cadence_pattern})
    if not slugs:
        return "(no cadence data — aim for 8-10 syllables per line)"
    placeholders = ",".join("?" * len(slugs))
    rows = db.execute(
        f"SELECT slug, syllable_template, stress_template, rhyme_compatibility, example_lines "
        f"FROM cadence_patterns WHERE slug IN ({placeholders})",
        slugs,
    ).fetchall()
    parts: list[str] = []
    for r in rows:
        examples = json.loads(r["example_lines"]) if r["example_lines"] else []
        line = f"  {r['slug']}: {r['syllable_template']} syll/line"
        if r["stress_template"]:
            line += f" | stress={r['stress_template']!r}"
        parts.append(line)
        if examples:
            parts.append(f'    e.g. "{examples[0]}"')
    return "\n".join(parts)


# ── Section block ─────────────────────────────────────────────────────────────

def _section_arc_hint(label: str, idx: int) -> str:
    ll = label.lower()
    if "intro" in ll:
        return "establish mood — no plot yet, just atmosphere"
    if "pre-chorus" in ll or "prechorus" in ll or "pre-hook" in ll:
        return "build tension toward the chorus"
    if "chorus" in ll or "hook" in ll or "refrain" in ll:
        return "emotional peak — the repeating core idea"
    if "bridge" in ll or "breakdown" in ll:
        return "pivot — shift perspective or reveal a twist"
    if "outro" in ll or "coda" in ll:
        return "close the arc — land the emotion"
    if "verse" in ll:
        return "set the scene and advance the story" if idx <= 1 else "deepen or complicate — do not repeat verse 1"
    return "develop the story"


def _section_block(sections: list[Section]) -> str:
    parts = []
    for idx, s in enumerate(sections):
        arc = _section_arc_hint(s.label, idx)
        parts.append(f"- id={s.id!r} label={s.label!r} cadence={s.cadence_pattern!r} → {arc}")
        if s.rhyme_scheme and s.rhyme_scheme != "free":
            parts.append(f"  rhyme: {s.rhyme_scheme}")
    return "\n".join(parts)


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_targets(song: Song, target_ids: set[str]) -> tuple[int, int, int]:
    passes = warns = fails = 0
    for s in song.sections:
        if s.id not in target_ids:
            continue
        for rule in ("singability", "cadence", "phonetic_texture", "rhyme_cadence", "story_sentence"):
            v = getattr(s.validation, rule)
            if v == "pass":
                passes += 1
            elif v == "warn":
                warns += 1
            elif v == "fail":
                fails += 1
    return passes, warns, fails


def _score_key(score: tuple[int, int, int]) -> tuple[int, int, int]:
    passes, warns, fails = score
    return (passes, -fails, -warns)


def _all_pass(song: Song, target_ids: set[str]) -> bool:
    GATED = ("singability", "phonetic_texture", "rhyme_cadence", "story_sentence")
    for s in song.sections:
        if s.id not in target_ids:
            continue
        for rule in GATED:
            v = getattr(s.validation, rule)
            if v in ("fail", "unrun"):
                return False
    return True


# ── Burn-list scrub ───────────────────────────────────────────────────────────

def _scrub_burn(lines: list[str], burn: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for line in lines:
        scrubbed = line
        for word, alts in burn.items():
            if alts:
                scrubbed = re.sub(rf"\b{re.escape(word)}\b", alts[0], scrubbed, flags=re.IGNORECASE)
        out.append(scrubbed)
    return out


# ── Apply lyrics / patches ────────────────────────────────────────────────────

def _apply_lyrics(song: Song, drafted_by_id: dict[str, Any], target_ids: set[str], burn: dict[str, list[str]]) -> None:
    for s in song.sections:
        if s.id not in target_ids:
            continue
        raw = drafted_by_id.get(s.id)
        if isinstance(raw, list):
            s.lyrics = _scrub_burn([str(x) for x in raw], burn)


# ── Repair support ────────────────────────────────────────────────────────────

def _build_failing_block(song: Song, target_ids: set[str]) -> str:
    """Build a compact block of ONLY the failing sections with their current lyrics + issues.
    Passing sections are omitted — that's the whole point.
    """
    parts: list[str] = []
    for s in song.sections:
        if s.id not in target_ids or not s.lyrics:
            continue
        section_issues = []
        for rule in ("singability", "phonetic_texture", "rhyme_cadence", "story_sentence"):
            v = getattr(s.validation, rule)
            if v in ("fail", "warn"):
                section_issues.append(f"{rule}:{v.upper()}")
        actionable = [w for w in (s.validation.warnings or []) if "cadence drift" not in w]
        if not section_issues and not actionable:
            continue
        parts.append(f"### Section {s.id} ({s.label}, cadence={s.cadence_pattern})")
        parts.append(f"  Issues: {', '.join(section_issues)}")
        for i, line in enumerate(s.lyrics):
            parts.append(f"  {i}: {line or '(blank)'}")
        if actionable:
            parts.append("  Specific problems:")
            for w in actionable[:6]:
                parts.append(f"    - {w}")
    return "\n".join(parts)


def _build_feedback(song: Song, target_ids: set[str]) -> str:
    """Legacy: full feedback block (used when no specific failing block available)."""
    parts: list[str] = []
    for s in song.sections:
        if s.id not in target_ids:
            continue
        issues = []
        for rule in ("singability", "phonetic_texture", "rhyme_cadence", "story_sentence"):
            v = getattr(s.validation, rule)
            if v in ("fail", "warn"):
                issues.append(f"{rule}: {v.upper()}")
        actionable = [w for w in (s.validation.warnings or []) if "cadence drift" not in w]
        if not issues and not actionable:
            continue
        parts.append(f"### Section {s.id} ({s.label})")
        if issues:
            parts.append("  Verdicts: " + ", ".join(issues))
        for w in actionable[:8]:
            parts.append(f"    - {w}")
    return "\n".join(parts) or "(no specific issues)"


# ── The loop ──────────────────────────────────────────────────────────────────

@router.post("/songs/{slug}/draft")
async def run_draft(
    slug: str,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    section: str | None = Query(None),
    max_attempts: int = Query(MAX_ATTEMPTS, ge=1, le=8),
    fix: bool = Query(False),
) -> dict:
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song = read_song(settings.songs_dir, slug)

    if not song.sections:
        song.sections = [
            Section(
                id=p["id"], label=p["label"], lock_state="draft",
                lyrics=[], cadence_pattern=p["cadence"],
            )
            for p in sections_for_genre(song.genre, song.sub_genre)
        ]

    if section is not None:
        targets = [s for s in song.sections if s.id == section]
        if not targets:
            raise HTTPException(404, f"section {section!r} not found in song")
    else:
        targets = [
            s for s in song.sections
            if s.lock_state != "locked" and (not s.lyrics or all(not l.strip() for l in s.lyrics))
        ]
        if not targets:
            raise HTTPException(409, "no empty unlocked sections to draft (use ?section=<id> to redraft one)")

    target_ids = {s.id for s in targets}

    # Pre-load shared context once
    burn = _load_burn_dict(db)
    burn_words_str = ", ".join(sorted(burn.keys())) or "(none)"
    raw_lens = _load_lens_brief(db, song.songwriter_lens)
    lens_brief_str = ("\nLENS: " + raw_lens) if raw_lens else ""
    cadence_compact = _load_cadence_compact(db, targets)
    initial_section_block = _section_block(targets)
    anchor_words_list, anchor_source, _ = resolve_vocab(
        db,
        genre=song.genre,
        emotion=song.intent.emotion_arc or "",
        topic=song.intent.topic or "",
        lens_slug=song.songwriter_lens or "",
    )
    anchor_words_str = ", ".join(anchor_words_list) if anchor_words_list else "(write to the topic directly)"
    world_str = _world_block(song)
    topic_short_str = _topic_short(song)
    genre_craft_str = _genre_craft_hint(song.genre, song.sub_genre)

    best_song: Song | None = None
    best_score: tuple[int, int, int] | None = None
    best_attempt_idx = -1
    attempt_log: list[dict] = []

    if fix and all(s.lyrics and any(l.strip() for l in s.lyrics) for s in targets):
        pre = song.model_copy(deep=True)
        validate_song(pre, db, include_llm=False)
        best_song = pre
        best_score = _score_targets(pre, target_ids)
        attempt_log.append({"attempt": "pre-fix-validation", "score": list(best_score)})

    for attempt in range(max_attempts):
        if best_song is None:
            # Initial draft — generate all target sections
            prompt = _INITIAL_PROMPT.format(
                world_block=world_str,
                topic_short=topic_short_str,
                genre=song.genre,
                sub_genre=song.sub_genre,
                lens_brief=lens_brief_str,
                genre_craft=genre_craft_str,
                section_block=initial_section_block,
                cadence_compact=cadence_compact,
                anchor_words=anchor_words_str,
                burn_words=burn_words_str,
            )
            task = "DRAFT"
        else:
            # Repair — only send failing sections, get back only those sections
            failing_block = _build_failing_block(best_song, target_ids)
            if not failing_block:
                break  # nothing left to fix
            prompt = _REPAIR_PROMPT.format(
                world_block=world_str,
                genre=song.genre,
                sub_genre=song.sub_genre,
                lens_brief=lens_brief_str,
                genre_craft=genre_craft_str,
                cadence_compact=cadence_compact,
                failing_block=failing_block,
                burn_words=burn_words_str,
            )
            task = "REPAIR"

        try:
            payload = ask_claude_json(prompt, task=task)
        except LLMError as e:
            if attempt == 0:
                raise HTTPException(502, f"LLM call failed on first attempt: {e}")
            break

        if not isinstance(payload, dict) or not isinstance(payload.get("sections"), list):
            if attempt == 0:
                raise HTTPException(502, "LLM returned malformed JSON (missing 'sections' array)")
            attempt_log.append({"attempt": attempt, "error": "malformed JSON; kept previous"})
            continue

        drafted_by_id: dict[str, Any] = {
            entry.get("id"): entry.get("lyrics")
            for entry in payload["sections"]
            if isinstance(entry, dict)
        }

        candidate = (best_song if best_song is not None else song).model_copy(deep=True)
        _apply_lyrics(candidate, drafted_by_id, target_ids, burn)
        validate_song(candidate, db, include_llm=False)

        score = _score_targets(candidate, target_ids)
        attempt_log.append({"attempt": attempt, "score": list(score), "task": task})

        if best_score is None or _score_key(score) > _score_key(best_score):
            best_score = score
            best_song = candidate
            best_attempt_idx = attempt

        if _all_pass(candidate, target_ids):
            break

    assert best_song is not None

    try:
        validate_song(best_song, db, include_llm=True, llm_section_ids=target_ids)
        best_score = _score_targets(best_song, target_ids)
    except Exception as e:
        attempt_log.append({"attempt": "final-llm-check", "error": str(e)})

    for src, dst in zip(best_song.sections, song.sections):
        if dst.id in target_ids:
            dst.lyrics = src.lyrics
            dst.validation = src.validation
            dst.lock_state = "draft" if dst.lock_state != "locked" else "locked"

    song.cohesion = best_song.cohesion
    song.last_modified_by = "api"
    song.modified = datetime.now(timezone.utc)

    try:
        from songwriter.api.main import app as _app
        w = getattr(_app.state, "watcher", None)
        if w is not None:
            w.note_self_write(slug)
    except Exception:
        pass

    write_song(settings.songs_dir, song)
    await ws_manager.broadcast(slug, {"type": "update", "song": song.model_dump(mode="json")})

    return {
        "song": song.model_dump(mode="json"),
        "draft": {
            "best_attempt": best_attempt_idx + 1,
            "attempts_used": len(attempt_log),
            "max_attempts": max_attempts,
            "best_score": {
                "passes": best_score[0] if best_score else 0,
                "warns":  best_score[1] if best_score else 0,
                "fails":  best_score[2] if best_score else 0,
            },
            "all_pass": _all_pass(song, target_ids),
            "anchor_words": {"count": len(anchor_words_list), "source": anchor_source},
            "log": attempt_log,
        },
    }
