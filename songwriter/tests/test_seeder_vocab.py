from pathlib import Path

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import (
    words as words_seeder,
    vocab_banks as vocab_seeder,
)


FIXTURE_CMUDICT = Path(__file__).parent / "fixtures" / "cmudict_vocab_words.txt"


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    words_seeder.seed_from_cmudict(target, FIXTURE_CMUDICT)
    return target


def test_seed_vocab_pop_confession(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)

    bank = conn.execute(
        "SELECT * FROM vocab_banks WHERE slug = 'pop.confession'"
    ).fetchone()
    assert bank is not None

    rows = conn.execute(
        """
        SELECT w.word FROM vocab_bank_words vbw
        JOIN words w ON w.id = vbw.word_id
        WHERE vbw.bank_id = ?
        """,
        (bank["id"],),
    ).fetchall()
    words = {r["word"] for r in rows}
    assert "voicemail" in words
    assert "receipt" in words


def test_seed_vocab_pop_banks(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)
    pop_banks = conn.execute(
        "SELECT slug FROM vocab_banks WHERE slug LIKE 'pop.%'"
    ).fetchall()
    slugs = {r["slug"] for r in pop_banks}
    assert {"pop.confession", "pop.infatuation", "pop.breakup",
            "pop.party", "pop.nostalgia", "pop.empowerment",
            "pop.intimacy", "pop.late-night"}.issubset(slugs)


def test_seed_vocab_flags_persist(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)
    row = conn.execute(
        """
        SELECT vbw.* FROM vocab_bank_words vbw
        JOIN vocab_banks vb ON vb.id = vbw.bank_id
        JOIN words w ON w.id = vbw.word_id
        WHERE vb.slug = 'pop.party' AND w.word = 'tonight'
        """
    ).fetchone()
    assert row is not None
    assert row["cliche_flag"] == 1


def test_seed_vocab_rnb_six_banks(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)
    rnb_banks = conn.execute(
        "SELECT slug FROM vocab_banks WHERE slug LIKE 'rnb.%'"
    ).fetchall()
    slugs = {r["slug"] for r in rnb_banks}
    assert {"rnb.intimacy", "rnb.longing", "rnb.seduction",
            "rnb.heartbreak", "rnb.late-night", "rnb.devotion"} == slugs


def test_seed_vocab_rnb_intimacy_collarbone(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)
    rows = conn.execute(
        """
        SELECT w.word FROM vocab_bank_words vbw
        JOIN vocab_banks vb ON vb.id = vbw.bank_id
        JOIN words w ON w.id = vbw.word_id
        WHERE vb.slug = 'rnb.intimacy'
        """
    ).fetchall()
    words = {r["word"] for r in rows}
    assert "collarbone" in words
    assert "shoulder" in words
