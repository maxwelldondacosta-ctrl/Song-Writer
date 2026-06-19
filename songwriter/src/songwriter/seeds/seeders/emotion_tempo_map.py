import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys
from songwriter.seeds.seeders.production_fingerprints import _resolve_sub_genre_id


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["entries"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for e in data["entries"]:
            require_keys(
                e, ["emotion", "sub_genre", "bpm_min", "bpm_max"],
                context=f"{yaml_path}#{e.get('emotion')}/{e.get('sub_genre')}",
            )
            sg_id = _resolve_sub_genre_id(conn, e["sub_genre"])
            conn.execute(
                """
                INSERT INTO emotion_tempo_map
                  (emotion, sub_genre_id, bpm_min, bpm_max, energy_curve, anti_prompts)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(emotion, sub_genre_id) DO UPDATE SET
                    bpm_min = excluded.bpm_min,
                    bpm_max = excluded.bpm_max,
                    energy_curve = excluded.energy_curve,
                    anti_prompts = excluded.anti_prompts
                """,
                (
                    e["emotion"], sg_id, e["bpm_min"], e["bpm_max"],
                    json.dumps(e.get("energy_curve") or []),
                    json.dumps(e.get("anti_prompts") or []),
                ),
            )
        conn.commit()
    finally:
        conn.close()
