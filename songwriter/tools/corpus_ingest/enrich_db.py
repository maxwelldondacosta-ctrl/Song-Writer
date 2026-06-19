"""Apply corpus findings into the songwriter DB.

Reads `derived_vocab.json`, `derived_artist_vocab.json`, `derived_cadence.json`,
`derived_cliches.json` (produced by `aggregate.py`) and writes new rows into
the appropriate tables.

Strategy:
  - Genre vocab: one bank per genre named `{genre}.corpus-canonical` containing
    the top TF-IDF-distinctive words. Last-DB-fallback for the resolver.
  - Artist vocab: one bank per artist named `{artist-slug}.corpus` containing
    words distinctive to that artist's 10-song corpus. Used by the lens system
    when adopting a specific songwriter's style.
  - Cadence: one new `cadence_patterns` row per (genre, kind) bucket whose
    median syllable template isn't already in the table.
  - Burn-list: extend with cross-artist cliché single words only — multi-word
    phrases don't fit the existing word-level scrub regex. Severity 'moderate'.

All inserts are guarded by slug/word existence checks → idempotent.

Defaults to **dry-run**. Use `--apply` to commit.

Usage:
  python -m tools.corpus_ingest.enrich_db                     # dry-run, all
  python -m tools.corpus_ingest.enrich_db --apply             # commit all
  python -m tools.corpus_ingest.enrich_db --artist-vocab      # only artist vocab (dry-run)
  python -m tools.corpus_ingest.enrich_db --artist-vocab --apply
  python -m tools.corpus_ingest.enrich_db --vocab             # only genre vocab
  python -m tools.corpus_ingest.enrich_db --cadence --apply
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "songwriter.db"
OUT_DIR = Path(__file__).resolve().parent


# ---------------- helpers ----------------

def _open_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit(f"DB not found at {DB_PATH}. Run songwriter-build first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_json(name: str) -> dict | list:
    p = OUT_DIR / name
    if not p.exists():
        sys.exit(
            f"{name} not found. Run `python -m tools.corpus_ingest.aggregate` first."
        )
    return json.loads(p.read_text())


def _word_id(conn: sqlite3.Connection, word: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM words WHERE word = ? AND language = 'en'", (word,)
    ).fetchone()
    return row["id"] if row else None


# ---------------- vocab enrichment ----------------

def enrich_vocab(conn: sqlite3.Connection, *, apply: bool, top_n: int = 25) -> dict:
    """Create `{genre}.corpus-canonical` banks from derived_vocab.json."""
    proposals: dict[str, list] = _load_json("derived_vocab.json")
    stats = {"banks_added": 0, "words_added": 0, "words_missing_from_words_table": 0,
             "skipped_existing": 0}

    for genre, words in sorted(proposals.items()):
        if not words:
            continue
        slug = f"{genre}.corpus-canonical"
        existing_bank = conn.execute(
            "SELECT id FROM vocab_banks WHERE slug = ?", (slug,)
        ).fetchone()

        candidate_words = words[:top_n]
        # Resolve word_ids first so we can show what's actually addable
        resolved: list[tuple[str, float, int, int]] = []
        unresolved: list[str] = []
        for w, score, df in candidate_words:
            wid = _word_id(conn, w)
            if wid is None:
                unresolved.append(w)
                stats["words_missing_from_words_table"] += 1
            else:
                resolved.append((w, score, df, wid))

        if not resolved:
            print(f"  [{genre}] skip — none of the top {len(candidate_words)} words "
                  f"are in `words` table (would need seeder run)")
            continue

        # Print before maybe writing
        verb = "would add" if not apply else "adding"
        print(f"  [{genre}] {verb} bank {slug!r} with {len(resolved)} words"
              f"{f' ({len(unresolved)} dropped — not in words table)' if unresolved else ''}")
        for w, score, df, _wid in resolved[:8]:
            print(f"      · {w} (score={score:.3f}, in {df} {genre} songs)")
        if len(resolved) > 8:
            print(f"      … +{len(resolved) - 8} more")

        if not apply:
            stats["banks_added"] += 1 if not existing_bank else 0
            stats["words_added"] += len(resolved)
            continue

        # WRITE
        if existing_bank:
            bank_id = existing_bank["id"]
            stats["skipped_existing"] += 1
        else:
            cur = conn.execute(
                "INSERT INTO vocab_banks (slug, name, description) VALUES (?, ?, ?)",
                (slug, f"{genre.title()} / corpus-canonical (auto-derived)",
                 f"Top TF-IDF-distinctive words across {genre} corpus. Coarse fallback for the resolver."),
            )
            bank_id = cur.lastrowid
            stats["banks_added"] += 1

        for w, score, df, wid in resolved:
            existing_link = conn.execute(
                "SELECT 1 FROM vocab_bank_words WHERE bank_id = ? AND word_id = ?",
                (bank_id, wid),
            ).fetchone()
            if existing_link:
                continue
            # Map TF-IDF score → emotional_weight (0.4..0.9 range)
            ew = max(0.4, min(0.9, 0.4 + score * 2))
            conn.execute(
                """
                INSERT INTO vocab_bank_words
                (bank_id, word_id, emotional_weight, imagery_class, cliche_flag, ai_bias_flag, notes)
                VALUES (?, ?, ?, ?, 0, 0, ?)
                """,
                (bank_id, wid, ew, "abstract",
                 f"corpus-derived: doc_freq={df}, tfidf={score:.4f}"),
            )
            stats["words_added"] += 1

    return stats


# ---------------- artist vocab enrichment ----------------

def enrich_artist_vocab(conn: sqlite3.Connection, *, apply: bool, top_n: int = 20) -> dict:
    """Create `{artist-slug}.corpus` vocab banks from derived_artist_vocab.json."""
    proposals: dict[str, list] = _load_json("derived_artist_vocab.json")
    stats = {"banks_added": 0, "words_added": 0, "words_missing": 0, "skipped_existing": 0}

    # Map artist_slug → display_name for the bank's human-readable name
    profile_names = {
        r["slug"]: r["display_name"]
        for r in conn.execute("SELECT slug, display_name FROM songwriter_profiles").fetchall()
    }

    for artist_slug, words in sorted(proposals.items()):
        if not words:
            continue
        display_name = profile_names.get(artist_slug, artist_slug)
        bank_slug = f"{artist_slug}.corpus"

        candidate_words = words[:top_n]
        resolved: list[tuple[str, float, int, int]] = []
        for w, score, df in candidate_words:
            wid = _word_id(conn, w)
            if wid is None:
                stats["words_missing"] += 1
            else:
                resolved.append((w, score, df, wid))

        if not resolved:
            print(f"  [{artist_slug}] skip — no words in `words` table")
            continue

        existing_bank = conn.execute(
            "SELECT id FROM vocab_banks WHERE slug = ?", (bank_slug,)
        ).fetchone()

        verb = "would add" if not apply else "adding"
        n_songs = words[0][2] if words else "?"  # doc_freq of top word as proxy
        print(f"  [{artist_slug}] {verb} bank {bank_slug!r} — "
              f"{len(resolved)} words resolved")
        for w, score, df, _wid in resolved[:6]:
            print(f"      · {w} (score={score:.3f}, in {df} songs)")
        if len(resolved) > 6:
            print(f"      … +{len(resolved) - 6} more")

        if not apply:
            stats["banks_added"] += 1 if not existing_bank else 0
            stats["words_added"] += len(resolved)
            continue

        if existing_bank:
            bank_id = existing_bank["id"]
            stats["skipped_existing"] += 1
        else:
            cur = conn.execute(
                "INSERT INTO vocab_banks (slug, name, description) VALUES (?, ?, ?)",
                (
                    bank_slug,
                    f"{display_name} / corpus",
                    f"Distinctive words from {display_name}'s Genius corpus "
                    f"(TF-IDF vs. all artists). Used by the lens system.",
                ),
            )
            bank_id = cur.lastrowid
            stats["banks_added"] += 1

        for w, score, df, wid in resolved:
            if conn.execute(
                "SELECT 1 FROM vocab_bank_words WHERE bank_id = ? AND word_id = ?",
                (bank_id, wid),
            ).fetchone():
                continue
            ew = max(0.4, min(0.9, 0.4 + score * 2))
            conn.execute(
                """
                INSERT INTO vocab_bank_words
                (bank_id, word_id, emotional_weight, imagery_class, cliche_flag, ai_bias_flag, notes)
                VALUES (?, ?, ?, ?, 0, 0, ?)
                """,
                (bank_id, wid, ew, "abstract",
                 f"corpus-derived: doc_freq={df}, tfidf={score:.4f}"),
            )
            stats["words_added"] += 1

    return stats


# ---------------- cadence enrichment ----------------

def enrich_cadence(conn: sqlite3.Connection, *, apply: bool, min_lines: int = 30) -> dict:
    """Add new cadence_patterns rows for observed (genre, kind) buckets that
    don't have an existing pattern at that median syllable count."""
    summary: dict = _load_json("derived_cadence.json")
    existing_slugs = {
        r["slug"] for r in conn.execute("SELECT slug FROM cadence_patterns").fetchall()
    }
    existing_sylls = {
        r["syllable_template"]
        for r in conn.execute("SELECT syllable_template FROM cadence_patterns").fetchall()
        if r["syllable_template"]
    }

    stats = {"added": 0, "skipped": 0}

    for key, s in sorted(summary.items()):
        if s["lines_seen"] < min_lines:
            stats["skipped"] += 1
            continue
        if s["syll_template"] in existing_sylls:
            stats["skipped"] += 1
            continue

        genre, kind = key.split(".", 1)
        slug = f"corpus-{genre}-{kind}"
        if slug in existing_slugs:
            stats["skipped"] += 1
            continue

        top_scheme = s["top_schemes"][0][0] if s["top_schemes"] else ""
        rhyme_compat = json.dumps({"end": [top_scheme]}) if top_scheme else json.dumps({})

        verb = "would add" if not apply else "adding"
        print(f"  {verb} cadence {slug!r}: {s['syll_template']} syll/line "
              f"(p25={s['syll_p25']}, p75={s['syll_p75']}), top_scheme={top_scheme}, "
              f"observed={s['lines_seen']} lines")

        if apply:
            conn.execute(
                """
                INSERT INTO cadence_patterns
                (slug, name, syllable_template, stress_template, typical_genres, example_lines, rhyme_compatibility)
                VALUES (?, ?, ?, '', ?, '[]', ?)
                """,
                (slug, f"{genre.title()} {kind} (corpus median)",
                 s["syll_template"], json.dumps([genre]), rhyme_compat),
            )
        stats["added"] += 1

    return stats


# ---------------- burn-list enrichment ----------------

def enrich_burn_list(conn: sqlite3.Connection, *, apply: bool, min_artists: int = 3,
                    min_count: int = 5) -> dict:
    """Add cross-artist cliché single words to suno_burn_list. Phrases reported but skipped."""
    cliches: list[dict] = _load_json("derived_cliches.json")
    existing = {
        r["word"].lower()
        for r in conn.execute("SELECT word FROM suno_burn_list").fetchall()
    }
    stats = {"added": 0, "skipped_existing": 0, "phrases_reported": 0}

    # Pull single-word ngrams (n=1 not present in our output, but n=3+ might
    # contain a content "core" word repeated. For now: skip phrases entirely
    # and only operate on the ngrams whose first content word recurs >= min_count.
    word_freq: dict[str, dict] = {}
    for c in cliches:
        if c["artists"] < min_artists or c["count"] < min_count:
            continue
        # Use the longest content word in the n-gram as the burn candidate
        # (skip stopwords-ish small words). Conservative: only burn if the same
        # 4+ char word appears in 3+ different cliché ngrams.
        for token in c["ngram"].split():
            if len(token) < 4:
                continue
            d = word_freq.setdefault(token, {"count": 0, "ngrams": set(), "artists": 0})
            d["count"] += c["count"]
            d["ngrams"].add(c["ngram"])
            d["artists"] = max(d["artists"], c["artists"])

    candidates = sorted(
        [(w, d) for w, d in word_freq.items() if len(d["ngrams"]) >= 2],
        key=lambda x: (-len(x[1]["ngrams"]), -x[1]["count"]),
    )[:25]

    for w, d in candidates:
        if w in existing:
            stats["skipped_existing"] += 1
            continue
        verb = "would add" if not apply else "adding"
        print(f"  {verb} burn word {w!r}: in {len(d['ngrams'])} cliché ngrams, "
              f"total count {d['count']}, max artists {d['artists']}")
        if apply:
            conn.execute(
                """
                INSERT INTO suno_burn_list (word, severity, drift_direction, alternatives)
                VALUES (?, 'mild', 'cliche', '[]')
                """,
                (w,),
            )
        stats["added"] += 1

    # Just report multi-word phrases — they won't fit our regex scrubber cleanly
    phrase_only = [c for c in cliches if c["artists"] >= min_artists and c["n"] >= 3][:10]
    if phrase_only:
        print(f"\n  multi-word cliché phrases (NOT inserted — scrubber is word-level):")
        for c in phrase_only:
            print(f"    · {c['ngram']!r} ({c['artists']} artists, count {c['count']})")
            stats["phrases_reported"] += 1

    return stats


# ---------------- driver ----------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Apply corpus findings to the DB")
    p.add_argument("--vocab", action="store_true", help="Enrich genre vocab_banks only")
    p.add_argument("--artist-vocab", action="store_true",
                   help="Enrich per-artist vocab banks only")
    p.add_argument("--cadence", action="store_true", help="Enrich cadence_patterns only")
    p.add_argument("--cliches", action="store_true", help="Enrich suno_burn_list only")
    p.add_argument("--apply", action="store_true",
                   help="Actually write changes (default: dry-run)")
    args = p.parse_args(argv)

    do_all = not (args.vocab or args.artist_vocab or args.cadence or args.cliches)

    conn = _open_db()
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== enrich_db ({mode}) ===\n")

    if do_all or args.vocab:
        print("--- GENRE VOCAB ---")
        s = enrich_vocab(conn, apply=args.apply)
        print(f"  → banks_added={s['banks_added']}, words_added={s['words_added']}, "
              f"words_dropped={s['words_missing_from_words_table']}\n")
        if args.apply:
            conn.commit()

    if do_all or args.artist_vocab:
        print("--- ARTIST VOCAB ---")
        s = enrich_artist_vocab(conn, apply=args.apply)
        print(f"  → banks_added={s['banks_added']}, words_added={s['words_added']}, "
              f"words_missing={s['words_missing']}\n")
        if args.apply:
            conn.commit()

    if do_all or args.cadence:
        print("--- CADENCE ---")
        s = enrich_cadence(conn, apply=args.apply)
        print(f"  → added={s['added']}, skipped={s['skipped']}\n")
        if args.apply:
            conn.commit()

    if do_all or args.cliches:
        print("--- BURN LIST ---")
        s = enrich_burn_list(conn, apply=args.apply)
        print(f"  → added={s['added']}, skipped_existing={s['skipped_existing']}, "
              f"phrases_reported={s['phrases_reported']}\n")
        if args.apply:
            conn.commit()

    if args.apply:
        print("✓ committed")
    else:
        print("(dry-run — no changes written. Re-run with --apply to commit.)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
