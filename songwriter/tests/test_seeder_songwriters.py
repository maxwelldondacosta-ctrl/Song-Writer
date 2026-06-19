import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import (
    genres as genres_seeder,
    songwriter_profiles as sw_seeder,
)


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    sw_seeder.seed_directory(target, DATA_DIR / "songwriters")
    return target


def test_pop_songwriters_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        """
        SELECT sp.slug FROM songwriter_profiles sp
        JOIN genres g ON g.id = sp.primary_genre_id
        WHERE g.slug = 'pop'
        """
    ).fetchall()
    slugs = {r["slug"] for r in rows}
    assert {"diane-warren", "max-martin", "julia-michaels", "finneas", "sia"} == slugs


def test_diane_warren_role_is_pure_songwriter(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM songwriter_profiles WHERE slug = 'diane-warren'"
    ).fetchone()
    assert row["role"] == "pure-songwriter"
    cs = json.loads(row["craft_signature"])
    assert isinstance(cs, list)
    assert any("belt" in line.lower() for line in cs)


def test_finneas_role_is_producer_songwriter(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT role FROM songwriter_profiles WHERE slug = 'finneas'"
    ).fetchone()
    assert row["role"] == "producer-songwriter"


def test_adoption_prompt_required(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        "SELECT slug, adoption_prompt FROM songwriter_profiles"
    ).fetchall()
    for r in rows:
        assert r["adoption_prompt"] and len(r["adoption_prompt"]) > 50, r["slug"]


def test_rnb_songwriters_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        """
        SELECT sp.slug FROM songwriter_profiles sp
        JOIN genres g ON g.id = sp.primary_genre_id
        WHERE g.slug = 'rnb'
        """
    ).fetchall()
    slugs = {r["slug"] for r in rows}
    assert {"frank-ocean", "the-dream", "babyface", "rodney-jerkins", "jam-and-lewis"} == slugs


def test_frank_ocean_role_is_self_writing(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT role FROM songwriter_profiles WHERE slug = 'frank-ocean'"
    ).fetchone()
    assert row["role"] == "self-writing-artist"


def test_total_phase1_profile_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM songwriter_profiles").fetchone()["c"]
    assert n >= 10  # 5 pop + 5 rnb baseline; additional genres extend


def test_role_distribution_covers_all_four_kinds(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        "SELECT DISTINCT role FROM songwriter_profiles"
    ).fetchall()
    roles = {r["role"] for r in rows}
    # Phase 1 must demonstrate all 4 role types so the lens-variation criterion
    # is testable.
    expected = {
        "pure-songwriter",
        "producer-songwriter",
        "singer-songwriter",
        "self-writing-artist",
    }
    assert expected <= roles
