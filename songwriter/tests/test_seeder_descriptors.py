import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import sonic_descriptors as desc_seeder


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    desc_seeder.seed(target, DATA_DIR / "descriptors" / "seeded.yml")
    return target


def test_seed_descriptors_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM artist_descriptor_cache"
    ).fetchone()["c"]
    assert n == 10


def test_seed_descriptors_normalizes_name(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM artist_descriptor_cache WHERE normalized_name = 'frank ocean'"
    ).fetchone()
    assert row is not None
    assert row["canonical_name"] == "Frank Ocean"
    assert row["source"] == "user-curated"
    assert row["quality_state"] == "pinned"


def test_seed_descriptors_short_is_under_30_words(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        "SELECT canonical_name, descriptor_short FROM artist_descriptor_cache"
    ).fetchall()
    for r in rows:
        n = len(r["descriptor_short"].split())
        assert n <= 30, f"{r['canonical_name']}: descriptor_short has {n} words"


def test_seed_descriptors_no_artist_name_inside_descriptor(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        "SELECT canonical_name, descriptor_short, descriptor_long FROM artist_descriptor_cache"
    ).fetchall()
    for r in rows:
        # the canonical name must not appear inside the rendered descriptors
        assert r["canonical_name"].lower() not in r["descriptor_short"].lower(), r["canonical_name"]
        assert r["canonical_name"].lower() not in r["descriptor_long"].lower(), r["canonical_name"]
