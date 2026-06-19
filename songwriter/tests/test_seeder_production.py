import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import (
    genres as genres_seeder,
    production_fingerprints as prod_seeder,
)


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    prod_seeder.seed(target, DATA_DIR / "production_fingerprints.yml")
    return target


def test_seed_production_fingerprints_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM production_fingerprints").fetchone()["c"]
    assert n >= 11  # 6 pop + 5 rnb baseline; additional sub-genres extend the count


def test_seed_production_alt_rnb_negatives(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        """
        SELECT pf.* FROM production_fingerprints pf
        JOIN sub_genres sg ON sg.id = pf.sub_genre_id
        WHERE sg.slug = 'alt-rnb'
        """
    ).fetchone()
    negs = json.loads(row["negative_descriptors"])
    assert any("bright" in n.lower() for n in negs)
