"""End-to-end build integration test using a small CMUdict fixture."""
from pathlib import Path

import pytest

from songwriter.seeds import build as build_module
from songwriter.seeds import db as db_module


FIXTURE_CMUDICT = (
    Path(__file__).parent / "fixtures" / "cmudict_vocab_words.txt"
)


def test_full_build_produces_populated_db(tmp_path, monkeypatch):
    target_db = tmp_path / "songwriter.db"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # Pre-seed the cache with our small fixture so build never hits the network
    fake_cmudict = cache_dir / "cmudict.dict"
    fake_cmudict.write_text(FIXTURE_CMUDICT.read_text())

    build_module.run(db_path=target_db, cache_dir=cache_dir)

    conn = db_module.connect(target_db)
    counts = {
        t: conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        for t in [
            "words", "genres", "sub_genres", "cadence_patterns",
            "structure_templates", "production_fingerprints",
            "emotion_tempo_map", "suno_burn_list",
            "vocab_banks", "vocab_bank_words",
            "songwriter_profiles", "artist_descriptor_cache",
        ]
    }
    assert counts["genres"] == 12
    assert counts["cadence_patterns"] == 10
    assert counts["structure_templates"] == 4
    assert counts["production_fingerprints"] >= 11
    assert counts["emotion_tempo_map"] >= 20
    assert counts["suno_burn_list"] >= 50
    assert counts["vocab_banks"] >= 12
    assert counts["vocab_bank_words"] >= 100
    assert counts["songwriter_profiles"] >= 10
    assert counts["artist_descriptor_cache"] == 10


def test_build_is_idempotent(tmp_path):
    target_db = tmp_path / "songwriter.db"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "cmudict.dict").write_text(FIXTURE_CMUDICT.read_text())

    build_module.run(db_path=target_db, cache_dir=cache_dir)
    build_module.run(db_path=target_db, cache_dir=cache_dir)

    conn = db_module.connect(target_db)
    n = conn.execute("SELECT COUNT(*) AS c FROM songwriter_profiles").fetchone()["c"]
    assert n >= 10
