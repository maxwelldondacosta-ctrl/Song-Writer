import sqlite3
from pathlib import Path

from songwriter.seeds import SCHEMA_PATH


EXPECTED_TABLES = {
    "words",
    "vocab_banks",
    "vocab_bank_words",
    "genres",
    "sub_genres",
    "cadence_patterns",
    "songwriter_profiles",
    "artist_descriptor_cache",
    "suno_burn_list",
    "structure_templates",
    "emotion_tempo_map",
    "production_fingerprints",
}


def test_schema_creates_all_expected_tables():
    sql = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    actual = {r[0] for r in rows}
    missing = EXPECTED_TABLES - actual
    assert not missing, f"missing tables: {missing}"


def test_words_table_has_expected_columns():
    sql = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(words)")}
    expected = {
        "id", "word", "language", "ipa", "arpabet",
        "syllables", "stress_pattern", "rhyme_class",
        "vowel_shape", "first_syllable_attack",
        "consonant_density", "syllable_count_class",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


from songwriter.seeds import db as db_module


def test_init_db_creates_file_with_tables(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    assert target.exists()
    import sqlite3
    conn = sqlite3.connect(target)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "words" in names
    assert "songwriter_profiles" in names


def test_init_db_is_idempotent(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    db_module.init_db(target)  # should not raise
    assert target.exists()


def test_connect_returns_row_factory(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    conn = db_module.connect(target)
    row = conn.execute("SELECT 1 AS x").fetchone()
    assert row["x"] == 1
