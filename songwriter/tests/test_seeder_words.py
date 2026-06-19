from pathlib import Path

import sqlite3
import pytest

from songwriter.seeds import db as db_module
from songwriter.seeds.seeders import words as words_seeder


FIXTURE = Path(__file__).parent / "fixtures" / "cmudict_sample.txt"


def test_seed_words_inserts_rows_with_derivations(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)

    inserted = words_seeder.seed_from_cmudict(target, FIXTURE)
    assert inserted >= 4  # love, heart, above, start

    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM words WHERE word = 'love' AND language = 'en'"
    ).fetchone()
    assert row is not None
    assert row["arpabet"] == "L AH1 V"
    assert row["ipa"] == "lʌv"
    assert row["syllables"] == 1
    assert row["stress_pattern"] == "1"
    assert row["rhyme_class"] == "AH-V"
    assert row["vowel_shape"] == "short-U"
    assert row["first_syllable_attack"] == "soft"
    assert row["consonant_density"] == pytest.approx(0.0)  # L is soft
    assert row["syllable_count_class"] == "mono"


def test_seed_words_is_idempotent(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    n1 = words_seeder.seed_from_cmudict(target, FIXTURE)
    n2 = words_seeder.seed_from_cmudict(target, FIXTURE)
    conn = db_module.connect(target)
    count = conn.execute("SELECT COUNT(*) AS c FROM words").fetchone()["c"]
    assert count == n1
    assert n2 == 0  # nothing new on second run
