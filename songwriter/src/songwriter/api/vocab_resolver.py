"""Anchor-word resolver for (genre, emotion, topic).

The seeded vocab_banks are keyed strictly by ``{genre}.{emotion}`` slugs that
match the seed data, e.g. ``rnb.heartbreak`` or ``pop.confession``. The
emotion arc on a song (preset or custom — ``surrender``, ``defiance``,
``quiet vindication``…) almost never matches a bank slug exactly, so before
this module nothing in the draft / alternatives flow ever read the banks.

This resolver tries, in order:
  1. **exact** — exact ``{genre}.{emotion}`` slug.
  2. **sibling-genre** — same genre, fuzzy emotion match (substring/synonym).
  3. **sibling-emotion** — same emotion across other genres.
  4. **llm-fallback** — ask Claude for 12-15 anchor words tailored to the
     (genre, emotion, topic) triple. Cached in-process so the same combo
     doesn't re-pay.
  5. **none** — empty list (fail-soft; caller decides if that's fatal).

Returns ``(words, source_label, bank_slug | None)``. The source label is
exposed in the draft response so the UI can flash "auto-LLM vocab used"
instead of silently shipping a draft with no anchoring.
"""

from __future__ import annotations

import sqlite3
from collections import OrderedDict
from typing import Generic, Literal, TypeVar

from songwriter.api.llm import LLMError, ask_claude_json


SourceLabel = Literal["exact", "sibling-genre", "sibling-emotion", "artist-corpus", "corpus", "llm-fallback", "none"]


_K = TypeVar("_K")
_V = TypeVar("_V")


class _LRU(Generic[_K, _V]):
    """Tiny bounded LRU. Insertion-order dict + pop-oldest when over capacity."""
    __slots__ = ("_d", "_cap")

    def __init__(self, cap: int) -> None:
        self._d: OrderedDict[_K, _V] = OrderedDict()
        self._cap = cap

    def get(self, key: _K) -> _V | None:
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def __contains__(self, key: _K) -> bool:
        return key in self._d

    def __getitem__(self, key: _K) -> _V:
        v = self._d[key]
        self._d.move_to_end(key)
        return v

    def __setitem__(self, key: _K, value: _V) -> None:
        self._d[key] = value
        self._d.move_to_end(key)
        while len(self._d) > self._cap:
            self._d.popitem(last=False)

    def clear(self) -> None:
        self._d.clear()

    def __len__(self) -> int:
        return len(self._d)


# Tiny synonym map so `surrender` finds `intimacy`-style banks within a genre,
# `defiance` finds `confrontation`/`empowerment`, etc. Keep it conservative —
# the LLM fallback handles anything we don't list here.
_EMOTION_KIN: dict[str, list[str]] = {
    "surrender":   ["intimacy", "devotion", "longing", "late-night", "letter"],
    "collapse":    ["heartbreak", "breakup", "destruction", "catharsis"],
    "redemption":  ["devotion", "witness", "family", "letter"],
    "defiance":    ["confrontation", "ambition", "system", "empowerment", "hustle"],
    "escalation":  ["bars", "come-up", "ambition", "confrontation", "destruction"],
    "nostalgia":   ["nostalgia", "small-town", "wandering", "letter", "landscape"],
    # extended: common custom arcs
    "heartbreak":  ["heartbreak", "breakup", "longing", "collapse"],
    "longing":     ["longing", "surrender", "late-night", "letter"],
    "celebration": ["celebration", "groove", "dance", "party"],
    "catharsis":   ["catharsis", "destruction", "road-escape", "friction"],
    "intimacy":    ["intimacy", "late-night", "devotion", "longing"],
    "hustle":      ["hustle", "come-up", "ambition", "bars"],
}


_LLM_CACHE: _LRU[tuple[str, str, str], list[str]] = _LRU(cap=256)


def reset_cache() -> None:
    """Test helper — clear the in-process LLM cache."""
    _LLM_CACHE.clear()


def _bank_words(db: sqlite3.Connection, slug: str, *, limit: int = 30) -> list[str]:
    rows = db.execute(
        """
        SELECT w.word FROM vocab_bank_words vbw
        JOIN words w ON w.id = vbw.word_id
        JOIN vocab_banks vb ON vb.id = vbw.bank_id
        WHERE vb.slug = ?
        ORDER BY vbw.emotional_weight DESC, w.word
        LIMIT ?
        """,
        (slug, limit),
    ).fetchall()
    return [r["word"] for r in rows]


def _exact(db: sqlite3.Connection, genre: str, emotion: str) -> list[str] | None:
    slug = f"{genre.lower()}.{emotion.lower()}"
    words = _bank_words(db, slug)
    return words or None


def _sibling_genre(
    db: sqlite3.Connection, genre: str, emotion: str
) -> tuple[list[str], str] | None:
    """Same genre, fuzzy emotion match. Substring + curated synonym map."""
    e = emotion.lower().strip()
    rows = db.execute(
        "SELECT slug FROM vocab_banks WHERE slug LIKE ?",
        (f"{genre.lower()}.%",),
    ).fetchall()
    candidates = [r["slug"] for r in rows]
    if not candidates:
        return None

    kin = set(_EMOTION_KIN.get(e, []))

    def score(slug: str) -> int:
        bank_e = slug.split(".", 1)[1]
        if bank_e == e:
            return 100
        if bank_e in kin:
            return 80
        if e and (e in bank_e or bank_e in e):
            return 50
        # Token overlap: "small-town" vs "small town", "late night" vs "late-night"
        e_toks = {t for t in e.replace("-", " ").split() if t}
        b_toks = {t for t in bank_e.replace("-", " ").split() if t}
        if e_toks & b_toks:
            return 30
        return 0

    candidates.sort(key=score, reverse=True)
    if score(candidates[0]) == 0:
        return None
    chosen = candidates[0]
    return _bank_words(db, chosen), chosen


def _artist_corpus(db: sqlite3.Connection, lens_slug: str) -> list[str] | None:
    """Per-artist corpus bank — words distinctive to this songwriter's catalog."""
    return _bank_words(db, f"{lens_slug}.corpus") or None


def _corpus_canonical(db: sqlite3.Connection, genre: str) -> list[str] | None:
    """Genre-level corpus bank — general anchor words derived from real songs."""
    return _bank_words(db, f"{genre.lower()}.corpus-canonical") or None


def _sibling_emotion(
    db: sqlite3.Connection, emotion: str
) -> tuple[list[str], str] | None:
    """Cross-genre emotion match — last sibling-bank attempt."""
    e = emotion.lower().strip()
    if not e:
        return None
    row = db.execute(
        "SELECT slug FROM vocab_banks WHERE slug LIKE ? ORDER BY slug LIMIT 1",
        (f"%.{e}",),
    ).fetchone()
    if not row:
        # Try kin words
        for kin_emotion in _EMOTION_KIN.get(e, []):
            row = db.execute(
                "SELECT slug FROM vocab_banks WHERE slug LIKE ? ORDER BY slug LIMIT 1",
                (f"%.{kin_emotion}",),
            ).fetchone()
            if row:
                break
    if not row:
        return None
    chosen = row["slug"]
    return _bank_words(db, chosen), chosen


_LLM_PROMPT = """\
List 14 concrete anchor words for songwriting in genre {genre!r} with the
emotional/topical register {emotion!r}{topic_clause}.

Bias toward 1-2 syllable nouns and verbs. Include 4-5 sensory specifics
(objects, places, body parts, fabrics, weather), 3-4 physical actions, and
2-3 register-specific verbs.

Avoid clichés (stars, neon, fire, ghost, tonight, ignite, forever, soul,
heart) and abstract emotion words (love, sad, happy, pain, hope). One word
per entry. Lowercase.

Output STRICT JSON in a fenced ```json block:
{{"words": ["w1", "w2", "w3", ...]}}
"""


def _llm_fallback(genre: str, emotion: str, topic: str) -> list[str] | None:
    key = (genre.lower().strip(), emotion.lower().strip(), topic.lower().strip())
    if key in _LLM_CACHE:
        return _LLM_CACHE[key]
    topic_clause = f" focused on the topic {topic!r}" if topic.strip() else ""
    prompt = _LLM_PROMPT.format(
        genre=genre, emotion=emotion, topic_clause=topic_clause,
    )
    try:
        payload = ask_claude_json(prompt)
    except LLMError:
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("words")
    if not isinstance(raw, list):
        return None
    cleaned: list[str] = []
    for w in raw:
        if not isinstance(w, str):
            continue
        s = w.strip().lower()
        # one-word entries only; no whitespace, no punctuation soup
        if not s or " " in s or len(s) > 25:
            continue
        cleaned.append(s)
    cleaned = cleaned[:15]
    if not cleaned:
        return None
    _LLM_CACHE[key] = cleaned
    return cleaned


def resolve_vocab(
    db: sqlite3.Connection,
    *,
    genre: str,
    emotion: str,
    topic: str = "",
    lens_slug: str = "",
) -> tuple[list[str], SourceLabel, str | None]:
    """Resolve anchor words for the given (genre, emotion, topic).

    When ``lens_slug`` is set (i.e. a songwriter lens is active), the
    per-artist corpus bank ``{lens_slug}.corpus`` is tried after the sibling
    lookups but before the genre-level corpus-canonical bank.

    Returns ``(words, source, bank_slug | None)``. ``words`` is empty only
    when every fallback fails (DB empty + LLM unreachable).
    """
    if not genre or not emotion:
        return [], "none", None

    if (words := _exact(db, genre, emotion)):
        return words, "exact", f"{genre.lower()}.{emotion.lower()}"

    if (sib := _sibling_genre(db, genre, emotion)):
        return sib[0], "sibling-genre", sib[1]

    if lens_slug and (artist := _artist_corpus(db, lens_slug)):
        return artist, "artist-corpus", f"{lens_slug}.corpus"

    if (cross := _sibling_emotion(db, emotion)):
        return cross[0], "sibling-emotion", cross[1]

    if (corpus := _corpus_canonical(db, genre)):
        return corpus, "corpus", f"{genre.lower()}.corpus-canonical"

    if (llm := _llm_fallback(genre, emotion, topic)):
        return llm, "llm-fallback", None

    return [], "none", None


# ----- emotion-tempo resolver (used by suno_prompt + coverage) -----

_EMOTION_TEMPO_CACHE: _LRU[tuple[str, str], dict] = _LRU(cap=256)


_TEMPO_PROMPT = """\
For a song in genre {genre!r} with sub-genre {sub_genre!r} and emotional
register {emotion!r}, suggest a BPM range and a short list of anti-prompt
phrases that would clash with this combination.

Output STRICT JSON in a fenced ```json block:
{{
  "bpm_min": <integer>,
  "bpm_max": <integer>,
  "anti_prompts": ["short phrase", "short phrase", ...]
}}

Rules:
- bpm_min/bpm_max must be plausible for the genre and emotion (e.g. soft rnb
  surrender: 60-80; defiant rap: 90-110). Return integers.
- 4-7 anti-prompt phrases. Short (≤4 words). No clichés.
"""


def reset_emotion_tempo_cache() -> None:
    _EMOTION_TEMPO_CACHE.clear()


def resolve_emotion_tempo(
    db: sqlite3.Connection,
    *,
    genre: str,
    sub_genre: str,
    emotion: str,
) -> tuple[dict, Literal["exact", "llm-fallback", "none"]]:
    """Returns ({bpm_min, bpm_max, anti_prompts, energy_curve?}, source).

    Source is 'exact' if the seed table had a direct match, 'llm-fallback' if
    Claude generated a plausible range, 'none' if both failed.
    """
    if not emotion:
        return {}, "none"

    # 1. DB exact match
    sg_row = db.execute(
        "SELECT id FROM sub_genres WHERE slug = ?", (sub_genre,),
    ).fetchone()
    sg_id = sg_row["id"] if sg_row else None
    if sg_id is not None:
        row = db.execute(
            "SELECT bpm_min, bpm_max, anti_prompts, energy_curve FROM emotion_tempo_map "
            "WHERE emotion = ? AND sub_genre_id = ?",
            (emotion, sg_id),
        ).fetchone()
        if row:
            import json as _json
            return ({
                "bpm_min": row["bpm_min"],
                "bpm_max": row["bpm_max"],
                "anti_prompts": _json.loads(row["anti_prompts"]) if row["anti_prompts"] else [],
                "energy_curve": _json.loads(row["energy_curve"]) if row["energy_curve"] else [],
            }, "exact")

    # 2. LLM fallback, cached
    key = (sub_genre.lower(), emotion.lower())
    cached = _EMOTION_TEMPO_CACHE.get(key)
    if cached is not None:
        return cached, "llm-fallback"

    try:
        payload = ask_claude_json(_TEMPO_PROMPT.format(
            genre=genre, sub_genre=sub_genre, emotion=emotion,
        ))
    except LLMError:
        return {}, "none"

    if not isinstance(payload, dict):
        return {}, "none"
    bpm_min = payload.get("bpm_min")
    bpm_max = payload.get("bpm_max")
    anti = payload.get("anti_prompts")
    if not (isinstance(bpm_min, int) and isinstance(bpm_max, int) and isinstance(anti, list)):
        return {}, "none"
    if not (40 <= bpm_min <= bpm_max <= 220):
        return {}, "none"

    result = {
        "bpm_min": bpm_min,
        "bpm_max": bpm_max,
        "anti_prompts": [str(a).strip() for a in anti if a][:8],
        "energy_curve": [],  # not asked of LLM
    }
    _EMOTION_TEMPO_CACHE[key] = result
    return result, "llm-fallback"


# ----- emotion-hardness classifier (used by phonetic_texture) -----

_HARDNESS_CACHE: _LRU[str, Literal["soft", "hard", "neutral"]] = _LRU(cap=256)

_HARDNESS_PROMPT = """\
Classify the emotional/sonic register of this emotion-arc word for songwriting:

EMOTION: {emotion!r}

Return STRICT JSON:
```json
{{"hardness": "soft" | "hard" | "neutral"}}
```

- "soft"   = vulnerable, intimate, melancholy, surrender, longing
- "hard"   = aggressive, defiant, urgent, escalating, confrontational
- "neutral" = neither dominant; mixed register
"""


def reset_hardness_cache() -> None:
    _HARDNESS_CACHE.clear()


def classify_emotion_hardness(emotion: str) -> Literal["soft", "hard", "neutral"]:
    """Return a soft/hard/neutral label for any emotion word, including custom.

    Cached per-process so a custom arc costs at most one LLM call per session.
    """
    e = (emotion or "").strip().lower()
    if not e:
        return "neutral"
    if e in _HARDNESS_CACHE:
        return _HARDNESS_CACHE[e]
    # Static fast path for the seeded preset set.
    if e in {"surrender", "nostalgia", "intimacy", "collapse", "longing", "redemption"}:
        _HARDNESS_CACHE[e] = "soft"
        return "soft"
    if e in {"defiance", "escalation", "confrontation", "destruction", "ambition"}:
        _HARDNESS_CACHE[e] = "hard"
        return "hard"
    try:
        payload = ask_claude_json(_HARDNESS_PROMPT.format(emotion=emotion))
    except LLMError:
        return "neutral"
    if not isinstance(payload, dict):
        return "neutral"
    val = payload.get("hardness")
    if val not in ("soft", "hard", "neutral"):
        return "neutral"
    _HARDNESS_CACHE[e] = val
    return val
