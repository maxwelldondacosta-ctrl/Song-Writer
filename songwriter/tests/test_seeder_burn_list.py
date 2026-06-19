import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import burn_list as burn_seeder


def test_seed_burn_list_minimum_count(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    burn_seeder.seed(target, DATA_DIR / "burn_list.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM suno_burn_list").fetchone()["c"]
    assert n >= 50


def test_seed_burn_list_neon_extreme(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    burn_seeder.seed(target, DATA_DIR / "burn_list.yml")
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM suno_burn_list WHERE word = 'neon'"
    ).fetchone()
    assert row["severity"] == "extreme"
    alts = json.loads(row["alternatives"])
    assert "argon" in alts
