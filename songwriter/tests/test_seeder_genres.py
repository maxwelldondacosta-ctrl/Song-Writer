from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import genres as genres_seeder


def test_seed_genres_loads_pop_and_rnb(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    conn = db_module.connect(target)

    pop = conn.execute("SELECT * FROM genres WHERE slug = 'pop'").fetchone()
    assert pop is not None
    assert pop["typical_bpm_min"] == 90

    pop_subs = conn.execute(
        "SELECT slug FROM sub_genres WHERE genre_id = ?", (pop["id"],)
    ).fetchall()
    slugs = {r["slug"] for r in pop_subs}
    assert {"dance-pop", "synth-pop", "indie-pop", "hyperpop", "alt-pop", "country-pop"} <= slugs


def test_seed_genres_has_all_12_top_level(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM genres").fetchone()["c"]
    assert n == 12


def test_seed_genres_is_idempotent(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM genres").fetchone()["c"]
    assert n == 12
