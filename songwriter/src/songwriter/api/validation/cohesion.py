"""Whole-song cohesion check.

The 5 per-section rules (Singability/Cadence/Phonetic-Texture/Rhyme-Cadence/
Story-Sentence) check that each section is internally sound and matches the
song's intent. Cohesion is a layer up: do verse 1, the chorus, verse 2, and
the bridge tell ONE coherent track when read in order?

This is LLM-judged. The deterministic engines can't catch:
- Verse 1 sets up someone leaving but verse 2 has them already gone in
  flashback without a bridge to mark the time-skip.
- Chorus introduces an image (a phone, a porch) that no verse ever picks up.
- Verse 2 contradicts verse 1's perspective (was 'I', now 'we' for no reason).
- Bridge introduces a totally new metaphor that doesn't pay off.
"""

from __future__ import annotations

from songwriter.api.llm import LLMError, ask_llm_json as ask_claude_json
from songwriter.api.schemas import CohesionIssue, CohesionValidation, Song
from songwriter.api.settings import get_settings


_PROMPT = """\
You are checking whether a song's sections cohere as ONE track. Output STRICT JSON.

## Song intent (the spec the song promised to deliver)
- Topic: {topic}
- Emotion arc: {emotion_arc}
- Story: event={event!r} | emotion={emotion!r} | resolution={resolution!r}

## Sections in order
{sections_block}

## What you are NOT checking
- Per-line grammar / rhyme / cadence — those are handled by other engines.
- Whether each section "fits the topic" alone — also handled elsewhere.

## What you ARE checking
1. **Narrative continuity.** Do the sections in order tell one story? Does the chorus refer back to images the verses introduced? Does the bridge actually pivot, or does it sit outside the song?
2. **Emotional arc.** Does the emotional progression match the spec'd arc (e.g. surrender means submission deepens; defiance means stakes rise)?
3. **Pronoun / perspective consistency.** "I" stays "I" unless there's a reason. "You" stays the same person.
4. **Image callbacks.** If verse 1 mentions a porch / a phone / a name, does the chorus or verse 2 pay it off? Or are images one-and-done with no echo?
5. **Contradictions.** Does any line undercut a claim made elsewhere in the song?

## Output schema (STRICT)
Wrap in a ```json fenced block:

{{
  "verdict": "pass" | "warn" | "fail",
  "summary": "<one short sentence — what the song is doing right or wrong as a whole track>",
  "issues": [
    {{ "section_ids": ["<id>", "<id>"], "note": "<specific cross-section problem>" }}
  ]
}}

- "verdict" rules:
    - "pass": the song reads as ONE coherent track. issues array is empty.
    - "warn": minor friction (one image isn't picked up, one perspective shift) — note in issues.
    - "fail": real cohesion problem (sections feel like different songs, or arc fights the spec).
- Each issue must name the specific section_ids involved.
- Empty issues = ok. Don't invent issues to look thorough.

Output ONLY the JSON block.
"""


def _format_sections_block(song: Song) -> str:
    parts: list[str] = []
    for s in song.sections:
        if not s.lyrics:
            parts.append(f"### {s.label} (id={s.id}) — empty")
            continue
        parts.append(f"### {s.label} (id={s.id})")
        for line in s.lyrics:
            parts.append(f"  {line or '(blank)'}")
    return "\n".join(parts) or "(no sections drafted yet)"


def check_song(song: Song) -> CohesionValidation:
    # Don't bother LLM-checking an empty song
    drafted = [s for s in song.sections if s.lyrics and any(l.strip() for l in s.lyrics)]
    if len(drafted) < 2:
        return CohesionValidation(
            verdict="unrun",
            summary="not enough drafted sections to check cohesion (need 2+)",
        )

    prompt = _PROMPT.format(
        topic=song.intent.topic or "(no topic)",
        emotion_arc=song.intent.emotion_arc or "(unspecified)",
        event=song.intent.story.event,
        emotion=song.intent.story.emotion,
        resolution=song.intent.story.resolution,
        sections_block=_format_sections_block(song),
    )

    try:
        payload = ask_claude_json(prompt, task="VALIDATE")
    except LLMError as e:
        return CohesionValidation(verdict="warn", summary=f"LLM cohesion check failed: {e}")

    if not isinstance(payload, dict):
        return CohesionValidation(verdict="warn", summary="LLM returned malformed cohesion JSON")

    verdict = payload.get("verdict", "warn")
    if verdict not in ("pass", "warn", "fail"):
        verdict = "warn"

    raw_issues = payload.get("issues") or []
    issues: list[CohesionIssue] = []
    for entry in raw_issues:
        if not isinstance(entry, dict) or not entry.get("note"):
            continue
        ids = entry.get("section_ids") or []
        if not isinstance(ids, list):
            ids = []
        issues.append(CohesionIssue(
            section_ids=[str(i) for i in ids],
            note=str(entry["note"]),
        ))

    return CohesionValidation(
        verdict=verdict,
        summary=str(payload.get("summary", "")),
        issues=issues,
    )
