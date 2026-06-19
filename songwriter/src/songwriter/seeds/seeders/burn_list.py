import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["words"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for w in data["words"]:
            require_keys(w, ["word", "severity"], context=f"{yaml_path}#{w.get('word')}")
            conn.execute(
                """
                INSERT INTO suno_burn_list (word, severity, drift_direction, alternatives)
                VALUES (?,?,?,?)
                ON CONFLICT(word) DO UPDATE SET
                    severity = excluded.severity,
                    drift_direction = excluded.drift_direction,
                    alternatives = excluded.alternatives
                """,
                (
                    w["word"].lower(), w["severity"],
                    w.get("drift_direction"),
                    json.dumps(w.get("alternatives") or []),
                ),
            )
        conn.commit()
    finally:
        conn.close()
