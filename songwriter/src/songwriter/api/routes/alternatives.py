"""POST /songs/{slug}/sections/{section_id}/lines/{line_index}/alternatives

Asks Claude (via subprocess, free) for N alternative versions of a single line,
constrained by the section's cadence + the lens + the song's intent + a
'distinct from this line' instruction. Returns alternatives without modifying
the song; the UI picks one and PUTs the song through the normal save path.

Two endpoint variants:
  POST .../alternatives           — synchronous JSON {alternatives: [...]}
  GET  .../alternatives/stream    — Server-Sent Events; one event per alt as
                                     it parses, plus a 'done' event at the end.
                                     Uses GET so EventSource works (no body).
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from songwriter.api.deps import get_db, get_settings
from songwriter.api.llm import LLMError, ask_claude_json
from songwriter.api.settings import Settings
from songwriter.api.songs_io import path_for_slug, read_song
from songwriter.api.vocab_resolver import resolve_vocab


router = APIRouter()


_PROMPT = """\
Suggest {count} alternative versions of ONE line in a song. Output STRICT JSON.

TOPIC: {topic}
EMOTION ARC: {emotion_arc}
STORY: event={event!r} | emotion={emotion!r} | resolution={resolution!r}
GENRE: {genre} / {sub_genre}
LENS: {lens_block}

ANCHOR WORDS (lean on these — concrete vocabulary tuned to the register):
{anchor_words}

CONTEXT (the section the line is in):
Section: {section_label}
Cadence: {cadence_compact}
Surrounding lyrics:
{context_block}

THE LINE TO REPLACE (line {line_index}):
{target_line!r}

EXTRA CONSTRAINT (from user, may be empty): {constraint}

RULES:
- Each alternative must serve the topic. No generic emotion words.
- Pull from the ANCHOR WORDS where they fit naturally; never force them.
- Keep within the section's cadence syllable target (±2).
- Each alternative must be DIFFERENT from the others — different imagery, different angle.
- Forbidden words: {burn_words}

Output JSON:
```json
{{"alternatives": ["line one", "line two", "line three"]}}
```
"""


def _load_lens(db: sqlite3.Connection, slug: str | None) -> str:
    """Same depth as draft.py — full adoption_prompt + craft + vocab."""
    if not slug:
        return "(no lens)"
    row = db.execute(
        """
        SELECT display_name, role, adoption_prompt, craft_signature,
               vocab_fingerprint, hook_style
        FROM songwriter_profiles WHERE slug = ?
        """,
        (slug,),
    ).fetchone()
    if not row:
        return f"({slug!r} not found)"
    parts: list[str] = [f"{row['display_name']} ({row['role']})"]
    ap = (row["adoption_prompt"] or "").strip()
    if ap:
        parts.append(ap)
    cs = json.loads(row["craft_signature"]) if row["craft_signature"] else []
    if cs:
        parts.append("Top craft cues:")
        for line in cs[:3]:
            parts.append(f"  - {line}")
    vf = json.loads(row["vocab_fingerprint"]) if row["vocab_fingerprint"] else {}
    if isinstance(vf, dict):
        sig = vf.get("signature_words") or []
        avoided = vf.get("avoided_words") or []
        if sig: parts.append(f"Signature words: {', '.join(sig)}")
        if avoided: parts.append(f"Avoid: {', '.join(avoided)}")
    if row["hook_style"]:
        parts.append(f"Hook style: {row['hook_style']}")
    return "\n".join(parts)


def _load_cadence_compact(db: sqlite3.Connection, slug: str) -> str:
    """Slug + syllable + stress + rhyme + example for the section's cadence."""
    row = db.execute(
        "SELECT syllable_template, stress_template, rhyme_compatibility, example_lines "
        "FROM cadence_patterns WHERE slug = ?",
        (slug,),
    ).fetchone()
    if not row:
        return "flexible"
    rc = json.loads(row["rhyme_compatibility"]) if row["rhyme_compatibility"] else {}
    examples = json.loads(row["example_lines"]) if row["example_lines"] else []
    line = f"{slug}: {row['syllable_template']} syll/line"
    if row["stress_template"]:
        line += f", stress={row['stress_template']!r}"
    if isinstance(rc, dict) and rc.get("end"):
        line += f", end-rhyme={','.join(rc['end'])}"
    if examples:
        line += f"\n    e.g. \"{examples[0]}\""
    return line


def _load_burn_words(db: sqlite3.Connection) -> list[str]:
    rows = db.execute(
        "SELECT word FROM suno_burn_list WHERE severity IN ('strong', 'extreme') ORDER BY word"
    ).fetchall()
    return [r["word"] for r in rows]


def _build_alts_prompt(
    db: sqlite3.Connection,
    song,
    section,
    line_index: int,
    count: int,
    constraint: str,
) -> tuple[str, str]:
    """Returns (prompt, target_line). Raises HTTPException on bounds errors."""
    if line_index < 0 or line_index >= len(section.lyrics):
        raise HTTPException(404, f"line {line_index} out of range for section {section.id!r}")
    target_line = section.lyrics[line_index]

    start = max(0, line_index - 2)
    end = min(len(section.lyrics), line_index + 3)
    context_lines = []
    for i in range(start, end):
        marker = "→" if i == line_index else " "
        context_lines.append(f"  {marker} {i}. {section.lyrics[i] or '(blank)'}")
    context_block = "\n".join(context_lines)

    burn = _load_burn_words(db)
    cadence_compact = _load_cadence_compact(db, section.cadence_pattern)
    lens_block = _load_lens(db, song.songwriter_lens)
    anchor_words_list, _, _ = resolve_vocab(
        db,
        genre=song.genre,
        emotion=song.intent.emotion_arc or "",
        topic=song.intent.topic or "",
        lens_slug=song.songwriter_lens or "",
    )
    anchor_words_str = ", ".join(anchor_words_list) if anchor_words_list else "(none — write to the topic directly)"

    prompt = _PROMPT.format(
        count=count,
        topic=song.intent.topic or "(no topic)",
        emotion_arc=song.intent.emotion_arc or "(unspecified)",
        event=song.intent.story.event,
        emotion=song.intent.story.emotion,
        resolution=song.intent.story.resolution,
        genre=song.genre,
        sub_genre=song.sub_genre,
        lens_block=lens_block,
        anchor_words=anchor_words_str,
        section_label=section.label,
        cadence_compact=cadence_compact,
        context_block=context_block,
        line_index=line_index,
        target_line=target_line,
        constraint=constraint or "(none)",
        burn_words=", ".join(burn) or "(none)",
    )
    return prompt, target_line


@router.post("/songs/{slug}/sections/{section_id}/lines/{line_index}/alternatives")
async def line_alternatives(
    slug: str,
    section_id: str,
    line_index: int,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    count: int = Query(3, ge=1, le=8),
    constraint: str = Query("", description="optional constraint, e.g. 'more vulnerable'"),
):
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song = read_song(settings.songs_dir, slug)
    section = next((s for s in song.sections if s.id == section_id), None)
    if not section:
        raise HTTPException(404, f"section {section_id!r} not found in song")

    prompt, target_line = _build_alts_prompt(db, song, section, line_index, count, constraint)

    try:
        payload = ask_claude_json(prompt)
    except LLMError as e:
        raise HTTPException(502, f"LLM call failed: {e}")

    if not isinstance(payload, dict) or not isinstance(payload.get("alternatives"), list):
        raise HTTPException(502, "LLM returned malformed JSON (missing 'alternatives' array)")

    alternatives = [str(a).strip() for a in payload["alternatives"] if a]
    return {
        "section_id": section_id,
        "line_index": line_index,
        "original": target_line,
        "alternatives": alternatives[:count],
    }


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/songs/{slug}/sections/{section_id}/lines/{line_index}/alternatives/stream")
async def line_alternatives_stream(
    slug: str,
    section_id: str,
    line_index: int,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    count: int = Query(3, ge=1, le=8),
    constraint: str = Query(""),
):
    """SSE variant — emits one event per candidate as it parses, then 'done'.

    Internally this still issues ONE claude --print call (cost-equivalent to
    the synchronous endpoint). The streaming is over the parse-and-yield step:
    each alternative is emitted with a short stagger so the UI gets visible
    progressive feedback during the ~5-15s LLM latency rather than a single
    big payload at the end.
    """
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song = read_song(settings.songs_dir, slug)
    section = next((s for s in song.sections if s.id == section_id), None)
    if not section:
        raise HTTPException(404, f"section {section_id!r} not found in song")

    prompt, target_line = _build_alts_prompt(db, song, section, line_index, count, constraint)

    async def gen() -> AsyncIterator[str]:
        # Initial event so the UI knows we're working
        yield _sse("started", {
            "section_id": section_id,
            "line_index": line_index,
            "original": target_line,
            "expected_count": count,
        })

        # Run the (blocking) subprocess in a worker thread so we don't stall
        # the event loop. Once it returns, parse and yield each candidate
        # with a small stagger.
        try:
            payload = await asyncio.to_thread(ask_claude_json, prompt)
        except LLMError as e:
            yield _sse("error", {"message": f"LLM call failed: {e}"})
            return

        if not isinstance(payload, dict) or not isinstance(payload.get("alternatives"), list):
            yield _sse("error", {"message": "LLM returned malformed JSON"})
            return

        alts = [str(a).strip() for a in payload["alternatives"] if a][:count]
        for i, alt in enumerate(alts):
            yield _sse("alt", {"index": i, "text": alt})
            # Small stagger so each candidate has visible appearance time.
            # 250ms × 3 = 750ms total; barely noticeable but kills the
            # 'all 3 appeared at once' jank.
            if i < len(alts) - 1:
                await asyncio.sleep(0.25)

        yield _sse("done", {"count": len(alts)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
