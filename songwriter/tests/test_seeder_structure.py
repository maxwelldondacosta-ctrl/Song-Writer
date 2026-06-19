import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import structure_templates as struct_seeder


def test_seed_structure_loads_4_templates(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    struct_seeder.seed(target, DATA_DIR / "structure_templates.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM structure_templates").fetchone()["c"]
    assert n == 4


def test_seed_structure_pop_standard(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    struct_seeder.seed(target, DATA_DIR / "structure_templates.yml")
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM structure_templates WHERE slug = 'pop.standard'"
    ).fetchone()
    sections = json.loads(row["sections"])
    assert sections[0]["section"] == "intro"
    chorus_sections = [s for s in sections if s["section"] == "chorus"]
    assert len(chorus_sections) == 3
