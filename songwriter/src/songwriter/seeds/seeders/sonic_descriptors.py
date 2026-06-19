import json
import re
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


_HONORIFICS = re.compile(r"\b(mr|mrs|ms|the|dj)\b\.?", re.IGNORECASE)


def _normalize(name: str) -> str:
    s = _HONORIFICS.sub("", name).strip().lower()
    s = re.sub(r"[^\w\s]", "", s)         # strip punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["descriptors"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for d in data["descriptors"]:
            require_keys(
                d,
                ["canonical_name", "descriptor_short", "descriptor_long", "source"],
                context=f"{yaml_path}#{d.get('canonical_name')}",
            )
            normalized = _normalize(d["canonical_name"])
            descriptor = d.get("descriptor") or d["descriptor_short"]
            conn.execute(
                """
                INSERT INTO artist_descriptor_cache
                  (normalized_name, canonical_name, era_label,
                   descriptor, descriptor_short, descriptor_long,
                   vocal_attributes, production_attrs, genre_context,
                   source, quality_state)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(normalized_name) DO UPDATE SET
                    canonical_name = excluded.canonical_name,
                    era_label = excluded.era_label,
                    descriptor = excluded.descriptor,
                    descriptor_short = excluded.descriptor_short,
                    descriptor_long = excluded.descriptor_long,
                    vocal_attributes = excluded.vocal_attributes,
                    production_attrs = excluded.production_attrs,
                    genre_context = excluded.genre_context,
                    source = excluded.source,
                    quality_state = excluded.quality_state
                """,
                (
                    normalized, d["canonical_name"], d.get("era_label"),
                    descriptor, d["descriptor_short"], d["descriptor_long"],
                    json.dumps(d.get("vocal_attributes") or {}),
                    json.dumps(d.get("production_attrs") or {}),
                    d.get("genre_context"),
                    d["source"], d.get("quality_state", "unverified"),
                ),
            )
        conn.commit()
    finally:
        conn.close()
