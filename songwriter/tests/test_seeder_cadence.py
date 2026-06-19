import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import cadence_patterns as cadence_seeder


def test_seed_cadence_loads_10(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    cadence_seeder.seed(target, DATA_DIR / "cadence_patterns.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM cadence_patterns").fetchone()["c"]
    assert n == 10


def test_seed_cadence_known_slugs(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    cadence_seeder.seed(target, DATA_DIR / "cadence_patterns.yml")
    conn = db_module.connect(target)
    slugs = {r["slug"] for r in conn.execute("SELECT slug FROM cadence_patterns")}
    expected = {
        "straight-4-beat", "double-time-rap", "triplet", "grime-swing",
        "melodic-glide", "punchline", "breakdown-chant", "pop-hook",
        "storytelling", "hybrid",
    }
    assert expected == slugs


def test_seed_cadence_json_columns_parse(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    cadence_seeder.seed(target, DATA_DIR / "cadence_patterns.yml")
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM cadence_patterns WHERE slug = 'melodic-glide'"
    ).fetchone()
    genres = json.loads(row["typical_genres"])
    assert "rnb" in genres
    rhyme = json.loads(row["rhyme_compatibility"])
    assert "perfect" in rhyme["end"]
