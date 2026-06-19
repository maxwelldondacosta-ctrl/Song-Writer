import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import (
    genres as genres_seeder,
    emotion_tempo_map as et_seeder,
)


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    et_seeder.seed(target, DATA_DIR / "emotion_tempo_map.yml")
    return target


def test_seed_emotion_tempo_alt_rnb_surrender(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        """
        SELECT et.* FROM emotion_tempo_map et
        JOIN sub_genres sg ON sg.id = et.sub_genre_id
        WHERE et.emotion = 'surrender' AND sg.slug = 'alt-rnb'
        """
    ).fetchone()
    assert row is not None
    assert row["bpm_min"] == 64
    assert row["bpm_max"] == 78
    anti = json.loads(row["anti_prompts"])
    assert "EDM-build" in anti


def test_seed_emotion_tempo_minimum_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM emotion_tempo_map").fetchone()["c"]
    assert n >= 20
