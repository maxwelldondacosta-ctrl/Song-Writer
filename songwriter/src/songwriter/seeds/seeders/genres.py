from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["genres"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for g in data["genres"]:
            require_keys(g, ["slug", "name"], context=f"{yaml_path}#{g.get('slug')}")
            conn.execute(
                """
                INSERT INTO genres (slug, name, description,
                                    typical_bpm_min, typical_bpm_max, notes_for_suno)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    typical_bpm_min = excluded.typical_bpm_min,
                    typical_bpm_max = excluded.typical_bpm_max,
                    notes_for_suno = excluded.notes_for_suno
                """,
                (
                    g["slug"], g["name"], g.get("description"),
                    g.get("typical_bpm_min"), g.get("typical_bpm_max"),
                    g.get("notes_for_suno"),
                ),
            )
            genre_id = conn.execute(
                "SELECT id FROM genres WHERE slug = ?", (g["slug"],)
            ).fetchone()["id"]
            for sg in g.get("sub_genres", []):
                require_keys(sg, ["slug", "name"], context=f"{yaml_path}#{g['slug']}/{sg.get('slug')}")
                conn.execute(
                    """
                    INSERT INTO sub_genres (genre_id, slug, name, description,
                                            typical_bpm_min, typical_bpm_max, notes_for_suno)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(genre_id, slug) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        typical_bpm_min = excluded.typical_bpm_min,
                        typical_bpm_max = excluded.typical_bpm_max,
                        notes_for_suno = excluded.notes_for_suno
                    """,
                    (
                        genre_id, sg["slug"], sg["name"], sg.get("description"),
                        sg.get("typical_bpm_min"), sg.get("typical_bpm_max"),
                        sg.get("notes_for_suno"),
                    ),
                )
        conn.commit()
    finally:
        conn.close()
