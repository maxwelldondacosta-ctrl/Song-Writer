import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


REQUIRED = ["slug", "display_name", "role", "primary_genre", "adoption_prompt"]
ALLOWED_ROLES = {
    "pure-songwriter",
    "producer-songwriter",
    "singer-songwriter",
    "self-writing-artist",
}


def _resolve_genre_id(conn, slug: str) -> int:
    row = conn.execute("SELECT id FROM genres WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise ValueError(f"unknown genre slug: {slug!r}")
    return row["id"]


def _seed_one(conn, data: dict, source: str) -> None:
    require_keys(data, REQUIRED, context=source)
    if data["role"] not in ALLOWED_ROLES:
        raise ValueError(f"{source}: invalid role {data['role']!r}")
    genre_id = _resolve_genre_id(conn, data["primary_genre"])
    conn.execute(
        """
        INSERT INTO songwriter_profiles
          (slug, display_name, real_name, era, primary_genre_id, role,
           sub_genres, notable_credits, craft_signature, personality_traits,
           writing_style, preferred_cadences, vocab_fingerprint,
           phonetic_fingerprint, structure_preferences, hook_style,
           reference_tracks, adoption_prompt)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            display_name = excluded.display_name,
            real_name = excluded.real_name,
            era = excluded.era,
            primary_genre_id = excluded.primary_genre_id,
            role = excluded.role,
            sub_genres = excluded.sub_genres,
            notable_credits = excluded.notable_credits,
            craft_signature = excluded.craft_signature,
            personality_traits = excluded.personality_traits,
            writing_style = excluded.writing_style,
            preferred_cadences = excluded.preferred_cadences,
            vocab_fingerprint = excluded.vocab_fingerprint,
            phonetic_fingerprint = excluded.phonetic_fingerprint,
            structure_preferences = excluded.structure_preferences,
            hook_style = excluded.hook_style,
            reference_tracks = excluded.reference_tracks,
            adoption_prompt = excluded.adoption_prompt
        """,
        (
            data["slug"], data["display_name"], data.get("real_name"),
            data.get("era"), genre_id, data["role"],
            json.dumps(data.get("sub_genres") or []),
            json.dumps(data.get("notable_credits") or []),
            json.dumps(data.get("craft_signature") or []),
            json.dumps(data.get("personality_traits") or []),
            json.dumps(data.get("writing_style") or {}),
            json.dumps(data.get("preferred_cadences") or []),
            json.dumps(data.get("vocab_fingerprint") or {}),
            json.dumps(data.get("phonetic_fingerprint") or {}),
            json.dumps(data.get("structure_preferences") or {}),
            data.get("hook_style"),
            json.dumps(data.get("reference_tracks") or []),
            data["adoption_prompt"],
        ),
    )


def seed_directory(db_path: Path, songwriters_dir: Path) -> None:
    conn = db_module.connect(db_path)
    try:
        for ext in ("*.yml", "*.yaml"):
            for p in sorted(songwriters_dir.rglob(ext)):
                data = load_yaml(p)
                _seed_one(conn, data, source=str(p))
        conn.commit()
    finally:
        conn.close()
