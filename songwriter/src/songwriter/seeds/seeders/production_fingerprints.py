import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def _resolve_sub_genre_id(conn, dotted: str) -> int:
    """Accept either 'genre.subgenre' or just 'subgenre' (must be unique)."""
    if "." in dotted:
        genre_slug, sub_slug = dotted.split(".", 1)
        row = conn.execute(
            """
            SELECT sg.id FROM sub_genres sg
            JOIN genres g ON g.id = sg.genre_id
            WHERE g.slug = ? AND sg.slug = ?
            """,
            (genre_slug, sub_slug),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM sub_genres WHERE slug = ?", (dotted,)
        ).fetchone()
    if not row:
        raise ValueError(f"unknown sub-genre: {dotted!r}")
    return row["id"]


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["fingerprints"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for fp in data["fingerprints"]:
            require_keys(fp, ["sub_genre"], context=f"{yaml_path}#{fp.get('sub_genre')}")
            sg_id = _resolve_sub_genre_id(conn, fp["sub_genre"])
            conn.execute(
                """
                INSERT INTO production_fingerprints
                  (sub_genre_id, instrumentation, vocal_style, mix_attributes,
                   positive_descriptors, negative_descriptors)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(sub_genre_id) DO UPDATE SET
                    instrumentation = excluded.instrumentation,
                    vocal_style = excluded.vocal_style,
                    mix_attributes = excluded.mix_attributes,
                    positive_descriptors = excluded.positive_descriptors,
                    negative_descriptors = excluded.negative_descriptors
                """,
                (
                    sg_id,
                    json.dumps(fp.get("instrumentation") or {}),
                    json.dumps(fp.get("vocal_style") or {}),
                    json.dumps(fp.get("mix_attributes") or {}),
                    json.dumps(fp.get("positive_descriptors") or []),
                    json.dumps(fp.get("negative_descriptors") or []),
                ),
            )
        conn.commit()
    finally:
        conn.close()
