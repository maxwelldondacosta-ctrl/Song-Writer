import json
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db


router = APIRouter()


def _row_to_dict(row: sqlite3.Row, json_cols: tuple[str, ...] = ()) -> dict:
    d = dict(row)
    for c in json_cols:
        if c in d and isinstance(d[c], str):
            try:
                d[c] = json.loads(d[c])
            except (TypeError, json.JSONDecodeError):
                pass
    return d


@router.get("/genres")
def list_genres(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM genres ORDER BY name").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/genres/{slug}")
def get_genre(slug: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    row = db.execute("SELECT * FROM genres WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise HTTPException(404, f"genre {slug!r} not found")
    out = _row_to_dict(row)
    sub_rows = db.execute(
        "SELECT * FROM sub_genres WHERE genre_id = ? ORDER BY name", (out["id"],)
    ).fetchall()
    out["sub_genres"] = [_row_to_dict(r) for r in sub_rows]
    return out


@router.get("/sub-genres")
def list_sub_genres(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute(
        """
        SELECT sg.*, g.slug AS parent_slug
        FROM sub_genres sg JOIN genres g ON g.id = sg.genre_id
        ORDER BY g.name, sg.name
        """
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/cadence-patterns")
def list_cadence_patterns(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM cadence_patterns ORDER BY slug").fetchall()
    return [_row_to_dict(r, ("typical_genres", "example_lines", "rhyme_compatibility")) for r in rows]


@router.get("/vocab-banks")
def list_vocab_banks(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM vocab_banks ORDER BY slug").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/vocab-banks/{slug}/words")
def get_vocab_bank_words(slug: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    bank = db.execute("SELECT id FROM vocab_banks WHERE slug = ?", (slug,)).fetchone()
    if not bank:
        raise HTTPException(404, f"vocab bank {slug!r} not found")
    rows = db.execute(
        """
        SELECT w.word, w.ipa, w.syllables, w.stress_pattern, w.rhyme_class,
               w.vowel_shape, w.first_syllable_attack, w.consonant_density,
               vbw.emotional_weight, vbw.imagery_class, vbw.cliche_flag, vbw.ai_bias_flag
        FROM vocab_bank_words vbw
        JOIN words w ON w.id = vbw.word_id
        WHERE vbw.bank_id = ?
        ORDER BY w.word
        """,
        (bank["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/words/{word}")
def get_word(word: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    row = db.execute(
        "SELECT * FROM words WHERE word = ? AND language = 'en'",
        (word.lower(),),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"word {word!r} not in dictionary")
    return dict(row)


@router.post("/words/lookup")
def lookup_words(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    payload: dict = None,
):
    """Bulk word lookup. Body: {"words": ["love", "above", ...]}.
    Returns: {"<word>": {phonetic data...}} for words found in the dictionary.
    Words not found are simply omitted from the response."""
    payload = payload or {}
    raw = payload.get("words")
    if not isinstance(raw, list):
        raise HTTPException(400, "body must be {\"words\": [string, ...]}")
    cleaned = list({str(w).lower().strip() for w in raw if isinstance(w, str) and w.strip()})
    if not cleaned:
        return {}
    placeholders = ",".join("?" * len(cleaned))
    rows = db.execute(
        f"""
        SELECT word, ipa, syllables, stress_pattern, rhyme_class, vowel_shape,
               first_syllable_attack, consonant_density
        FROM words
        WHERE word IN ({placeholders}) AND language = 'en'
        """,
        cleaned,
    ).fetchall()
    return {r["word"]: dict(r) for r in rows}


@router.get("/rhymes")
def get_rhymes(
    word: str,
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: int = Query(50, ge=1, le=500),
):
    base = db.execute(
        "SELECT rhyme_class FROM words WHERE word = ? AND language = 'en'",
        (word.lower(),),
    ).fetchone()
    if not base or not base["rhyme_class"]:
        raise HTTPException(404, f"no rhyme data for {word!r}")
    rc = base["rhyme_class"]
    rows = db.execute(
        """
        SELECT word, ipa, syllables, stress_pattern, vowel_shape,
               first_syllable_attack, consonant_density
        FROM words
        WHERE rhyme_class = ? AND language = 'en' AND word != ?
        ORDER BY syllables, word
        LIMIT ?
        """,
        (rc, word.lower(), limit),
    ).fetchall()
    return {"rhyme_class": rc, "words": [dict(r) for r in rows]}


@router.get("/burn-list")
def list_burn_list(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM suno_burn_list ORDER BY severity DESC, word").fetchall()
    return [_row_to_dict(r, ("alternatives",)) for r in rows]
