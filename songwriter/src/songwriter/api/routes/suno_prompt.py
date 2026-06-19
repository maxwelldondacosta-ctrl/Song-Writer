"""POST /songs/{slug}/suno-prompt — assemble a Suno-ready prompt deterministically.

The prompt is built from the song JSON + DB context (production fingerprint,
emotion-tempo, songwriter lens, burn list). No LLM call — this is templating.
The result writes to song.suno_prompt.current and appends to .history.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from songwriter.api.deps import get_db, get_settings
from songwriter.api.schemas import Song
from songwriter.api.settings import Settings
from songwriter.api.songs_io import path_for_slug, read_song, write_song
from songwriter.api.ws import manager as ws_manager


router = APIRouter()


def _resolve_sub_genre(db: sqlite3.Connection, dotted: str) -> tuple[int | None, str | None]:
    """Returns (sub_genre_id, sub_genre.slug) or (None, None)."""
    if "." in dotted:
        g_slug, sg_slug = dotted.split(".", 1)
        row = db.execute(
            """
            SELECT sg.id, sg.slug FROM sub_genres sg JOIN genres g ON g.id = sg.genre_id
            WHERE g.slug = ? AND sg.slug = ?
            """,
            (g_slug, sg_slug),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT id, slug FROM sub_genres WHERE slug = ?", (dotted,)
        ).fetchone()
    return (row["id"], row["slug"]) if row else (None, None)


def _load_production(db: sqlite3.Connection, sub_genre_id: int | None) -> dict:
    if sub_genre_id is None:
        return {}
    row = db.execute(
        "SELECT * FROM production_fingerprints WHERE sub_genre_id = ?", (sub_genre_id,)
    ).fetchone()
    if not row:
        return {}
    out = dict(row)
    for c in ("instrumentation", "vocal_style", "mix_attributes",
              "positive_descriptors", "negative_descriptors"):
        out[c] = json.loads(out[c]) if out.get(c) else None
    return out


def _load_emotion_tempo(db: sqlite3.Connection, emotion: str, sub_genre_id: int | None) -> dict:
    if sub_genre_id is None or not emotion:
        return {}
    row = db.execute(
        "SELECT * FROM emotion_tempo_map WHERE emotion = ? AND sub_genre_id = ?",
        (emotion, sub_genre_id),
    ).fetchone()
    if not row:
        return {}
    return {
        "bpm_min": row["bpm_min"],
        "bpm_max": row["bpm_max"],
        "anti_prompts": json.loads(row["anti_prompts"]) if row["anti_prompts"] else [],
        "energy_curve": json.loads(row["energy_curve"]) if row["energy_curve"] else [],
    }


def _load_lens(db: sqlite3.Connection, slug: str | None) -> dict:
    if not slug:
        return {}
    row = db.execute(
        """
        SELECT display_name, role, hook_style, craft_signature, vocab_fingerprint, phonetic_fingerprint
        FROM songwriter_profiles WHERE slug = ?
        """,
        (slug,),
    ).fetchone()
    if not row:
        return {}
    out = dict(row)
    for c in ("craft_signature", "vocab_fingerprint", "phonetic_fingerprint"):
        out[c] = json.loads(out[c]) if out.get(c) else None
    return out


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


def _scrub(text: str, burn: dict[str, list[str]]) -> str:
    out = text
    for word, alts in burn.items():
        if not alts:
            continue
        out = re.sub(rf"\b{re.escape(word)}\b", alts[0], out, flags=re.IGNORECASE)
    return out


def _section_summary(song: Song) -> str:
    """Concise 'Verse 1, Chorus, Verse 2, Chorus, Bridge, Chorus' style summary."""
    if not song.sections:
        return "verse / chorus / verse / chorus structure"
    return ", ".join(s.label for s in song.sections)


_TAG_KIND = re.compile(r"\b(verse|chorus|bridge|pre[- ]?chorus|hook|intro|outro|drop|breakdown|refrain)\b", re.IGNORECASE)


def _label_to_suno_tag(label: str) -> str:
    """Map a section label like 'Verse 1', 'Chorus', 'Pre-Chorus' to Suno's
    `[Verse 1]`, `[Chorus]`, `[Pre-Chorus]` tag format."""
    label = label.strip()
    if not label:
        return "[Verse]"
    m = _TAG_KIND.search(label)
    if not m:
        return f"[{label}]"
    kind = m.group(0).strip().title().replace(" ", "-")
    # Pull a number suffix if present
    num_match = re.search(r"\b(\d+)\b", label)
    if num_match:
        return f"[{kind} {num_match.group(1)}]"
    return f"[{kind}]"


def _build_structure_tags_block(song: Song) -> str:
    """Return a single line like:
    Structure: [Verse 1] [Chorus] [Verse 2] [Chorus] [Bridge] [Chorus]
    Suno's docs and Lyria's docs both call out structure tags as required for
    the model to keep section boundaries straight. Without them, Suno fuses
    or inverts sections — explicitly named in r/SunoAI / hookgenius failure
    breakdowns from the last 30 days.
    """
    if not song.sections:
        return ""
    tags = " ".join(_label_to_suno_tag(s.label) for s in song.sections)
    return tags


def _energy_arc_phrase(curve: list[float]) -> str:
    if not curve:
        return ""
    if len(curve) < 2:
        return ""
    if curve[-1] > curve[0] + 0.15:
        return "energy builds across the song"
    if curve[-1] < curve[0] - 0.15:
        return "energy descends across the song"
    peak_idx = curve.index(max(curve))
    if peak_idx >= len(curve) - 2:
        return "energy peaks at the end"
    if peak_idx <= 1:
        return "energy peaks early then sustains"
    return "energy peaks mid-song"


def build_suno_prompt(song: Song, db: sqlite3.Connection, *, allow_llm_fallback: bool = True) -> dict:
    """Returns {prompt, anti_prompts, sections, warnings, sources}.
    `sections` is the structured 9-section breakdown for UI display.
    `warnings` lists DB lookups that came back empty (and weren't recovered).
    `sources` records which path (exact/llm-fallback) each lookup took.
    Set `allow_llm_fallback=False` to force a deterministic, no-LLM build.
    """
    from songwriter.api.vocab_resolver import resolve_emotion_tempo

    sg_id, sg_slug = _resolve_sub_genre(db, song.sub_genre)
    prod = _load_production(db, sg_id)
    et = _load_emotion_tempo(db, song.intent.emotion_arc, sg_id)
    lens = _load_lens(db, song.songwriter_lens)
    burn = _load_burn_dict(db)

    warnings: list[str] = []
    sources: dict[str, str] = {}
    et_source = "exact" if et else "none"

    # If the DB entry was missing AND fallback is allowed, ask Claude.
    if not et and song.intent.emotion_arc and allow_llm_fallback:
        et_resolved, et_source = resolve_emotion_tempo(
            db,
            genre=song.genre,
            sub_genre=sg_slug or song.sub_genre,
            emotion=song.intent.emotion_arc,
        )
        if et_resolved:
            et = et_resolved
    sources["emotion_tempo"] = et_source

    if sg_id is None:
        warnings.append(f"sub-genre {song.sub_genre!r} not in DB — prompt missing production fingerprint")
    elif not prod:
        warnings.append(f"no production_fingerprint row for {sg_slug or song.sub_genre!r} — vocal/instrumentation/mood lines dropped")
    if song.intent.emotion_arc and not et:
        warnings.append(f"no emotion_tempo entry for {song.intent.emotion_arc!r} × {sg_slug or song.sub_genre!r} — BPM lock + anti-prompts dropped")
    if song.songwriter_lens and not lens:
        warnings.append(f"songwriter lens {song.songwriter_lens!r} not found — style line dropped")

    # 1. Genre line
    genre_line = f"{song.genre.upper()} / {sg_slug or song.sub_genre}"

    # 2. BPM line
    if et.get("bpm_min") and et.get("bpm_max"):
        bpm_line = f"{et['bpm_min']}–{et['bpm_max']} BPM"
    elif song.production.bpm:
        bpm_line = f"{song.production.bpm} BPM"
    else:
        bpm_line = ""

    # 3. Vocal line — pull from production fingerprint's vocal_style
    vocal_bits: list[str] = []
    vs = prod.get("vocal_style") or {}
    for k in ("delivery", "effects"):
        v = vs.get(k)
        if isinstance(v, list):
            vocal_bits.extend(v)
    if lens.get("phonetic_fingerprint"):
        pf = lens["phonetic_fingerprint"]
        if isinstance(pf, dict) and pf.get("attack_profile"):
            vocal_bits.append(f"{pf['attack_profile']} attack")
    vocal_line = ", ".join(vocal_bits) if vocal_bits else ""

    # 4. Production / instrumentation line
    instr_bits: list[str] = []
    instr = prod.get("instrumentation") or {}
    for k in ("drums", "bass", "keys", "guitars"):
        v = instr.get(k)
        if isinstance(v, list):
            instr_bits.extend(v[:2])  # cap to keep terse
    mix = prod.get("mix_attributes") or {}
    mix_bits = [f"{k}={v}" for k, v in mix.items()] if isinstance(mix, dict) else []
    production_line = ", ".join(instr_bits + mix_bits) if (instr_bits or mix_bits) else ""

    # 5. Section dynamics
    section_line = _section_summary(song)
    arc = _energy_arc_phrase(song.production.energy_curve)
    if arc:
        section_line = f"{section_line} — {arc}"

    # 5b. Suno structure tags — explicit [Verse]/[Chorus]/[Bridge] markers.
    structure_tags = _build_structure_tags_block(song)

    # 6. Lens craft cues
    lens_line = ""
    if lens:
        cs = lens.get("craft_signature") or []
        first_cue = cs[0] if cs else ""
        hook = lens.get("hook_style") or ""
        bits = [b for b in (lens.get("display_name", ""), hook, first_cue) if b]
        lens_line = " — ".join(bits)

    # 7. Mood / positive texture
    pos = prod.get("positive_descriptors") or []
    mood_line = ", ".join(pos[:6])

    # 8. Anti-prompts
    anti: set[str] = set()
    for s in (prod.get("negative_descriptors") or []):
        anti.add(s)
    for s in (et.get("anti_prompts") or []):
        anti.add(s)

    # 9. Lyric structure note
    lyric_line = f"clean, original lyrics. structure: {section_line}"

    sections_dict = {
        "genre": genre_line,
        "bpm": bpm_line,
        "vocal": vocal_line,
        "production": production_line,
        "dynamics": section_line,
        "structure_tags": structure_tags,
        "lens": lens_line,
        "mood": mood_line,
        "anti": ", ".join(sorted(anti)) if anti else "",
        "lyric_note": lyric_line,
    }

    # Concatenate non-empty parts into a single Suno-ready prompt.
    lines: list[str] = []
    if genre_line: lines.append(genre_line)
    if bpm_line: lines.append(bpm_line)
    if vocal_line: lines.append(f"Vocals: {vocal_line}")
    if production_line: lines.append(f"Production: {production_line}")
    if mood_line: lines.append(f"Mood: {mood_line}")
    if section_line: lines.append(f"Arrangement: {section_line}")
    if structure_tags: lines.append(f"Structure: {structure_tags}")
    if lens_line: lines.append(f"Style: {lens_line}")

    main_prompt = ". ".join(lines).strip()
    if main_prompt and not main_prompt.endswith("."):
        main_prompt += "."

    main_prompt = _scrub(main_prompt, burn)
    sorted_anti = sorted(anti)

    return {
        "prompt": main_prompt,
        "anti_prompts": sorted_anti,
        "sections": sections_dict,
        "warnings": warnings,
        "sources": sources,
    }


@router.post("/songs/{slug}/suno-prompt")
async def run_build_suno_prompt(
    slug: str,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
) -> dict:
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song = read_song(settings.songs_dir, slug)

    built = build_suno_prompt(song, db)

    # Append previous prompt to history before overwriting
    if song.suno_prompt.current:
        song.suno_prompt.history.append({
            "prompt": song.suno_prompt.current,
            "replaced_at": datetime.now(timezone.utc).isoformat(),
        })
    song.suno_prompt.current = built["prompt"]

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
        "warnings": built.get("warnings", []),
        "sources": built.get("sources", {}),
    }
