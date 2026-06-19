import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["templates"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for t in data["templates"]:
            require_keys(t, ["slug", "name", "sections"], context=f"{yaml_path}#{t.get('slug')}")
            conn.execute(
                """
                INSERT INTO structure_templates
                  (slug, name, sections, genre_compatibility)
                VALUES (?,?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    sections = excluded.sections,
                    genre_compatibility = excluded.genre_compatibility
                """,
                (
                    t["slug"], t["name"],
                    json.dumps(t["sections"]),
                    json.dumps(t.get("genre_compatibility") or []),
                ),
            )
        conn.commit()
    finally:
        conn.close()
