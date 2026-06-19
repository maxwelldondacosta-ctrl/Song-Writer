import re
import sqlite3
from dataclasses import dataclass


@dataclass
class WordToken:
    word: str
    unknown: bool
    syllables: int
    stress_pattern: str
    rhyme_class: str
    vowel_shape: str
    first_syllable_attack: str
    consonant_density: float
    ipa: str


_WORD_RE = re.compile(r"[a-z']+", re.IGNORECASE)


def tokenize_line(line: str, conn: sqlite3.Connection) -> list[WordToken]:
    raw_words = [m.group(0).lower().strip("'") for m in _WORD_RE.finditer(line)]
    raw_words = [w for w in raw_words if w]
    if not raw_words:
        return []
    placeholders = ",".join("?" * len(raw_words))
    rows = conn.execute(
        f"""
        SELECT word, syllables, stress_pattern, rhyme_class, vowel_shape,
               first_syllable_attack, consonant_density, ipa
        FROM words WHERE word IN ({placeholders}) AND language = 'en'
        """,
        raw_words,
    ).fetchall()
    by_word = {r["word"]: r for r in rows}
    out: list[WordToken] = []
    for w in raw_words:
        r = by_word.get(w)
        if r is None:
            out.append(WordToken(
                word=w, unknown=True, syllables=0, stress_pattern="",
                rhyme_class="", vowel_shape="", first_syllable_attack="",
                consonant_density=0.0, ipa="",
            ))
        else:
            out.append(WordToken(
                word=w, unknown=False,
                syllables=r["syllables"] or 0,
                stress_pattern=r["stress_pattern"] or "",
                rhyme_class=r["rhyme_class"] or "",
                vowel_shape=r["vowel_shape"] or "",
                first_syllable_attack=r["first_syllable_attack"] or "",
                consonant_density=r["consonant_density"] or 0.0,
                ipa=r["ipa"] or "",
            ))
    return out
