from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys
from songwriter.seeds.gruut_fallback import ipa_for_word


def _ensure_word(conn, word: str, language: str = "en") -> int:
    """Look up word_id; if missing, insert via gruut fallback (ipa only)."""
    row = conn.execute(
        "SELECT id FROM words WHERE word = ? AND language = ?", (word, language)
    ).fetchone()
    if row:
        return row["id"]
    ipa = ipa_for_word(word, language)
    conn.execute(
        "INSERT INTO words (word, language, ipa) VALUES (?,?,?)",
        (word, language, ipa),
    )
    return conn.execute(
        "SELECT id FROM words WHERE word = ? AND language = ?", (word, language)
    ).fetchone()["id"]


def _seed_one_bank(conn, data: dict, source: str) -> None:
    require_keys(data, ["slug", "name", "words"], context=source)
    conn.execute(
        """
        INSERT INTO vocab_banks (slug, name, description)
        VALUES (?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            description = excluded.description
        """,
        (data["slug"], data["name"], data.get("description")),
    )
    bank_id = conn.execute(
        "SELECT id FROM vocab_banks WHERE slug = ?", (data["slug"],)
    ).fetchone()["id"]
    for w in data["words"]:
        if "word" not in w:
            raise ValueError(f"{source}: word entry missing 'word'")
        word_id = _ensure_word(conn, w["word"].lower())
        conn.execute(
            """
            INSERT INTO vocab_bank_words
              (bank_id, word_id, emotional_weight, imagery_class,
               cliche_flag, ai_bias_flag, notes)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(bank_id, word_id) DO UPDATE SET
                emotional_weight = excluded.emotional_weight,
                imagery_class = excluded.imagery_class,
                cliche_flag = excluded.cliche_flag,
                ai_bias_flag = excluded.ai_bias_flag,
                notes = excluded.notes
            """,
            (
                bank_id, word_id,
                w.get("emotional_weight"),
                w.get("imagery_class"),
                1 if w.get("cliche_flag") else 0,
                1 if w.get("ai_bias_flag") else 0,
                w.get("notes"),
            ),
        )


def seed_directory(db_path: Path, vocab_dir: Path) -> None:
    """Seed every YAML file under `vocab_dir` (recursive)."""
    conn = db_module.connect(db_path)
    try:
        for ext in ("*.yml", "*.yaml"):
            for p in sorted(vocab_dir.rglob(ext)):
                data = load_yaml(p)
                _seed_one_bank(conn, data, source=str(p))
        conn.commit()
    finally:
        conn.close()
