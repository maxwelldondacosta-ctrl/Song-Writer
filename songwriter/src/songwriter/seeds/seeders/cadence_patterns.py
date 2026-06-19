import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["patterns"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for p in data["patterns"]:
            require_keys(p, ["slug", "name"], context=f"{yaml_path}#{p.get('slug')}")
            conn.execute(
                """
                INSERT INTO cadence_patterns
                  (slug, name, syllable_template, stress_template,
                   typical_genres, example_lines, rhyme_compatibility)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    syllable_template = excluded.syllable_template,
                    stress_template = excluded.stress_template,
                    typical_genres = excluded.typical_genres,
                    example_lines = excluded.example_lines,
                    rhyme_compatibility = excluded.rhyme_compatibility
                """,
                (
                    p["slug"], p["name"],
                    p.get("syllable_template"), p.get("stress_template"),
                    json.dumps(p.get("typical_genres") or []),
                    json.dumps(p.get("example_lines") or []),
                    json.dumps(p.get("rhyme_compatibility") or {}),
                ),
            )
        conn.commit()
    finally:
        conn.close()
