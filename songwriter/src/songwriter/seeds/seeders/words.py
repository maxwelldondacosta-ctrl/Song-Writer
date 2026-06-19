from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds import cmudict
from songwriter.seeds.arpabet_ipa import arpabet_to_ipa
from songwriter.seeds.derived import (
    syllable_count,
    syllable_count_class,
    stress_pattern,
    rhyme_class,
    vowel_shape,
    first_syllable_attack,
    consonant_density,
)


def seed_from_cmudict(db_path: Path, cmudict_path: Path) -> int:
    """Insert CMUdict words into `words` table. Returns number of new rows."""
    entries = cmudict.parse_file(cmudict_path)
    conn = db_module.connect(db_path)
    inserted = 0
    try:
        existing = {
            row["word"]
            for row in conn.execute(
                "SELECT word FROM words WHERE language = 'en'"
            )
        }
        rows = []
        for word, arpabet in entries.items():
            if word in existing:
                continue
            try:
                ipa = arpabet_to_ipa(arpabet)
                syl = syllable_count(arpabet)
                rows.append((
                    word, "en", ipa, arpabet,
                    syl, stress_pattern(arpabet), rhyme_class(arpabet),
                    vowel_shape(arpabet), first_syllable_attack(arpabet),
                    consonant_density(arpabet), syllable_count_class(syl),
                ))
            except (ValueError, IndexError):
                continue
        if rows:
            conn.executemany(
                """
                INSERT INTO words
                  (word, language, ipa, arpabet, syllables, stress_pattern,
                   rhyme_class, vowel_shape, first_syllable_attack,
                   consonant_density, syllable_count_class)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )
            inserted = len(rows)
        conn.commit()
    finally:
        conn.close()
    return inserted
