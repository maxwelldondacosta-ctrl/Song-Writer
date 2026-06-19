"""Aggregate per-song stats into genre-level and artist-level findings.

Reads every `*.stats.json` in the cache, joins to `songwriter_profiles` for
the artist→genre mapping, and rolls up:

  Per (genre, section_kind):
    - syllable distribution (p25/p50/p75) → suggested cadence syll template
    - rhyme scheme tally → most common scheme (AABB / ABAB / ABCB / ...)
    - top content words

  Per genre:
    - top n-grams (3, 4, 5) → cliché candidates for burn-list extension
    - vocab fingerprint candidates (TF-IDF vs other genres)

  Per artist:
    - TF-IDF distinctive words (artist corpus vs. all-artist corpus)
    - dominant section structure and rhyme schemes

  Diff against existing DB:
    - words proposed for vocab_banks that aren't already there
    - cadence syllable templates that don't match existing patterns
    - 3-grams that recur in ≥3 artists within a genre → cliché alerts

Outputs:
  tools/corpus_ingest/findings.md              — human-readable report
  tools/corpus_ingest/derived_vocab.json       — proposed genre vocab additions
  tools/corpus_ingest/derived_artist_vocab.json — per-artist distinctive word lists
  tools/corpus_ingest/derived_cliches.json     — proposed burn-list extensions
  tools/corpus_ingest/derived_cadence.json     — observed cadence patterns

Usage:
  python -m tools.corpus_ingest.aggregate
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = Path(__file__).resolve().parent / "cache"
OUT_DIR = Path(__file__).resolve().parent
DB_PATH = REPO_ROOT / "data" / "songwriter.db"


# ---------------- DB helpers ----------------

def _artist_to_genre(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT sp.slug, g.slug AS genre
        FROM songwriter_profiles sp
        JOIN genres g ON g.id = sp.primary_genre_id
        """
    ).fetchall()
    out = {}
    for r in rows:
        # The fetch script may have stripped "Jimmy Jam & Terry Lewis" → "Jimmy Jam"
        # but the cache dir uses Genius's resolved name. Index on profile slug AND
        # the simplified single-name slug.
        out[r["slug"]] = r["genre"]
        if "-and-" in r["slug"]:
            head = r["slug"].split("-and-")[0]
            out[head] = r["genre"]
    return out


def _existing_vocab_words(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT w.word FROM vocab_bank_words vbw JOIN words w ON w.id = vbw.word_id
        """
    ).fetchall()
    return {r["word"] for r in rows}


def _existing_cadence_syllables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT syllable_template FROM cadence_patterns").fetchall()
    return {r["syllable_template"] for r in rows if r["syllable_template"]}


def _existing_burn_words(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT word FROM suno_burn_list").fetchall()
    return {r["word"].lower() for r in rows}


# ---------------- corpus loader ----------------

def _load_corpus() -> list[dict]:
    """Return list of per-song stats dicts, with artist_slug + genre attached."""
    out: list[dict] = []
    for stats_file in CACHE_DIR.glob("*/*.stats.json"):
        try:
            d = json.loads(stats_file.read_text())
            d["_path"] = str(stats_file)
            out.append(d)
        except Exception as e:
            print(f"  ! skip {stats_file.name}: {e}", file=sys.stderr)
    return out


# ---------------- per-genre, per-section rollup ----------------

def _quantile(vals: list[int], q: float) -> int:
    if not vals:
        return 0
    s = sorted(vals)
    idx = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[idx]


def _section_rollups(songs: list[dict], a2g: dict[str, str]) -> dict:
    """Roll up per (genre, kind): syll dist, scheme tally, top words."""
    bucket: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"sylls": [], "schemes": Counter(), "words": Counter(), "songs": 0}
    )
    for song in songs:
        genre = a2g.get(song["artist_slug"])
        if not genre:
            continue
        for sec in song["sections"]:
            kind = sec["kind"]
            if kind in ("part-marker", "intro", "outro", "interlude"):
                continue  # too noisy for cadence aggregation
            b = bucket[(genre, kind)]
            b["songs"] += 1
            for s in sec["syll_per_line"]:
                if s > 0:
                    b["sylls"].append(s)
            if sec["rhyme_scheme"] and len(sec["rhyme_scheme"]) >= 2:
                b["schemes"][sec["rhyme_scheme"]] += 1
            for w, n in sec["top_words"]:
                b["words"][w] += n

    summary: dict = {}
    for (genre, kind), b in bucket.items():
        if not b["sylls"]:
            continue
        summary[f"{genre}.{kind}"] = {
            "songs": b["songs"],
            "lines_seen": len(b["sylls"]),
            "syll_p25":   _quantile(b["sylls"], 0.25),
            "syll_p50":   _quantile(b["sylls"], 0.50),
            "syll_p75":   _quantile(b["sylls"], 0.75),
            "syll_template": str(_quantile(b["sylls"], 0.50)),
            "top_schemes": b["schemes"].most_common(5),
            "top_words":   b["words"].most_common(40),
        }
    return summary


# ---------------- TF-IDF-ish per-genre vocab proposal ----------------

def _genre_vocab_candidates(songs: list[dict], a2g: dict[str, str]) -> dict[str, list[tuple[str, float, int]]]:
    """For each genre, surface words that are FREQUENT in this genre and
    INFREQUENT in others. Returns {genre: [(word, score, count), ...]}.
    """
    per_genre_counts: dict[str, Counter[str]] = defaultdict(Counter)
    per_genre_song_count: dict[str, int] = Counter()

    for song in songs:
        genre = a2g.get(song["artist_slug"])
        if not genre:
            continue
        per_genre_song_count[genre] += 1
        seen_in_song: set[str] = set()
        for w, n in song["top_words"]:
            if w in seen_in_song:
                continue
            seen_in_song.add(w)
            per_genre_counts[genre][w] += 1  # document frequency, not raw count

    genres = list(per_genre_counts.keys())
    n_genres = len(genres)
    if n_genres == 0:
        return {}

    # Document frequency across genres
    df_across_genres: Counter[str] = Counter()
    for g in genres:
        for w in per_genre_counts[g]:
            df_across_genres[w] += 1

    proposals: dict[str, list[tuple[str, float, int]]] = {}
    for g in genres:
        n_songs_g = per_genre_song_count[g]
        if n_songs_g < 2:
            continue
        scores: list[tuple[str, float, int]] = []
        for w, df_g in per_genre_counts[g].items():
            if df_g < 2:
                continue  # only one song mentions it — too noisy
            tf = df_g / n_songs_g  # share of songs in this genre containing w
            idf = math.log(n_genres / df_across_genres[w])
            score = tf * idf
            if score > 0:
                scores.append((w, round(score, 4), df_g))
        scores.sort(key=lambda x: x[1], reverse=True)
        proposals[g] = scores[:25]
    return proposals


# ---------------- per-artist TF-IDF vocab ----------------

def _artist_vocab_candidates(songs: list[dict]) -> dict[str, list[tuple[str, float, int]]]:
    """For each artist, surface words that are frequent in their songs and
    distinctive vs. the full artist pool (TF-IDF across artists).
    Returns {artist_slug: [(word, score, doc_freq_within_artist), ...]}.
    """
    per_artist_df: dict[str, Counter[str]] = defaultdict(Counter)
    per_artist_song_count: dict[str, int] = Counter()

    for song in songs:
        slug = song["artist_slug"]
        per_artist_song_count[slug] += 1
        seen_in_song: set[str] = set()
        for w, _n in song["top_words"]:
            if w not in seen_in_song:
                seen_in_song.add(w)
                per_artist_df[slug][w] += 1  # how many of this artist's songs contain w

    n_artists = len(per_artist_song_count)
    if n_artists == 0:
        return {}

    # Cross-artist document frequency: how many distinct artists use each word
    cross_df: Counter[str] = Counter()
    for artist_slug, word_counts in per_artist_df.items():
        for w in word_counts:
            cross_df[w] += 1

    proposals: dict[str, list[tuple[str, float, int]]] = {}
    for artist_slug, word_counts in per_artist_df.items():
        n_songs = per_artist_song_count[artist_slug]
        if n_songs < 2:
            continue
        scores: list[tuple[str, float, int]] = []
        for w, df in word_counts.items():
            if df < 2:
                continue  # appears in only 1 song — too sparse
            tf = df / n_songs
            idf = math.log(n_artists / cross_df[w])
            score = tf * idf
            if score > 0:
                scores.append((w, round(score, 4), df))
        scores.sort(key=lambda x: x[1], reverse=True)
        proposals[artist_slug] = scores[:30]

    return proposals


# ---------------- cliché n-gram detection ----------------

_LINE_RE = re.compile(r"[a-z']+")


def _line_words(line: str) -> list[str]:
    return [w.strip("'") for w in _LINE_RE.findall(line.lower()) if w.strip("'")]


def _cliche_ngrams(songs: list[dict], a2g: dict[str, str]) -> dict:
    """Cross-corpus n-gram counts. Returns {n: [(ngram, count, n_artists), ...]}."""
    artist_ngrams: dict[int, dict[str, set[str]]] = {3: defaultdict(set), 4: defaultdict(set), 5: defaultdict(set)}
    raw_counts: dict[int, Counter[str]] = {3: Counter(), 4: Counter(), 5: Counter()}

    # We need to re-derive line text from the original cache, since stats files
    # don't store full lyric strings. So join back via the cache .json for ngrams.
    for stats_file_path in CACHE_DIR.glob("*/*.stats.json"):
        artist_slug = stats_file_path.parent.name
        if artist_slug not in a2g:
            continue
        raw_path = stats_file_path.with_suffix("")  # drop .stats.json suffix
        # Actually .with_suffix only strips one extension; we need to strip ".stats"
        raw_path = stats_file_path.parent / stats_file_path.name.replace(".stats.json", ".json")
        if not raw_path.exists():
            continue
        try:
            song = json.loads(raw_path.read_text())
        except Exception:
            continue
        for line in song["lyrics"].splitlines():
            line = line.strip()
            if not line or line.startswith("[") or line.endswith("Embed"):
                continue
            words = _line_words(line)
            for n in (3, 4, 5):
                if len(words) < n:
                    continue
                for i in range(len(words) - n + 1):
                    ng = " ".join(words[i:i + n])
                    raw_counts[n][ng] += 1
                    artist_ngrams[n][ng].add(artist_slug)

    out: dict = {}
    for n in (3, 4, 5):
        items = []
        for ng, c in raw_counts[n].items():
            n_artists = len(artist_ngrams[n][ng])
            if n_artists < 3:  # only flag if it shows up across ≥3 different artists
                continue
            items.append((ng, c, n_artists))
        items.sort(key=lambda x: (-x[2], -x[1]))  # most artists first, then count
        out[n] = items[:30]
    return out


# ---------------- diff vs DB ----------------

def _diff_vocab(proposals: dict, existing: set[str]) -> dict:
    """Filter genre vocab proposals to NEW words not already in any vocab bank."""
    novel: dict[str, list] = {}
    for g, words in proposals.items():
        new_only = [(w, score, df) for (w, score, df) in words if w not in existing]
        novel[g] = new_only[:20]
    return novel


def _diff_cadence(section_summary: dict, existing_sylls: set[str]) -> list[dict]:
    """List section-rollups whose median syll template isn't in the DB."""
    out = []
    for key, s in section_summary.items():
        if s["syll_template"] not in existing_sylls and s["lines_seen"] >= 30:
            out.append({"key": key, **s})
    return out


def _diff_cliches(ngram_findings: dict, existing_burn: set[str]) -> list[dict]:
    """3-grams (and longer) that appear across many artists and aren't already burnt."""
    out = []
    for n, items in ngram_findings.items():
        for ng, count, n_artists in items:
            # skip if any token of the ngram is already burnt at the word level
            if any(t in existing_burn for t in ng.split()):
                continue
            out.append({"ngram": ng, "n": n, "count": count, "artists": n_artists})
    out.sort(key=lambda d: (-d["artists"], -d["count"]))
    return out[:60]


# ---------------- report writer ----------------

def _write_findings(
    section_summary: dict,
    vocab_proposals: dict,
    novel_vocab: dict,
    artist_vocab: dict,
    cliche_alerts: list,
    cadence_gaps: list,
    n_songs: int,
) -> None:
    lines = [
        "# Corpus Ingest Findings",
        "",
        f"_Generated from {n_songs} songs in `tools/corpus_ingest/cache/`._",
        "",
        "## Cadence templates per (genre, section)",
        "",
        "Median syllable count across all observed lines. p25/p75 give the spread.",
        "",
        "| Bucket | Songs | Lines | p25 | **p50** | p75 | Top scheme |",
        "|---|---|---|---|---|---|---|",
    ]
    for key in sorted(section_summary):
        s = section_summary[key]
        top_scheme = s["top_schemes"][0][0] if s["top_schemes"] else "—"
        lines.append(
            f"| `{key}` | {s['songs']} | {s['lines_seen']} | "
            f"{s['syll_p25']} | **{s['syll_p50']}** | {s['syll_p75']} | `{top_scheme}` |"
        )

    lines.extend([
        "",
        "## Cadence templates NOT YET in `cadence_patterns`",
        "",
        "These observed median templates aren't matched by any existing pattern in the DB.",
        "",
    ])
    if not cadence_gaps:
        lines.append("_(none — every observed median is already covered)_")
    else:
        for cg in cadence_gaps:
            lines.append(f"- **{cg['key']}** → `{cg['syll_template']}` syll/line "
                         f"(seen {cg['lines_seen']}× across {cg['songs']} sections)")

    lines.extend([
        "",
        "## Genre vocab proposals (TF-IDF-ranked, NEW words only)",
        "",
        "Words that recur in this genre's corpus but aren't in any existing vocab bank.",
        "Score = (genre document frequency) × log(n_genres / cross-genre DF).",
        "",
    ])
    for genre in sorted(novel_vocab):
        words = novel_vocab[genre]
        if not words:
            continue
        lines.append(f"### {genre}")
        lines.append("")
        for w, score, df in words:
            lines.append(f"  - `{w}` (score={score}, in {df} {genre} songs)")
        lines.append("")

    lines.extend([
        "## Per-artist vocab fingerprints (TF-IDF distinctive words)",
        "",
        "Words that recur in this artist's songs and are rare across other artists.",
        "Score = (artist song frequency) × log(n_artists / cross-artist DF).",
        "",
    ])
    for artist_slug in sorted(artist_vocab):
        words = artist_vocab[artist_slug]
        if not words:
            continue
        lines.append(f"### {artist_slug}")
        lines.append("")
        for w, score, df in words[:15]:
            lines.append(f"  - `{w}` (score={score}, in {df} songs)")
        lines.append("")

    lines.extend([
        "## Cliché alerts (n-grams across ≥3 artists)",
        "",
        "Phrases that recur across multiple artists and aren't already in the burn-list.",
        "Strong candidates for `suno_burn_list` extension.",
        "",
    ])
    for c in cliche_alerts[:40]:
        lines.append(f"- `{c['ngram']}` — n={c['n']}, count={c['count']}, artists={c['artists']}")

    lines.append("")
    OUT_DIR.joinpath("findings.md").write_text("\n".join(lines))


# ---------------- main ----------------

def main() -> int:
    if not DB_PATH.exists():
        sys.exit(f"DB not found at {DB_PATH}. Run songwriter-build first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    a2g = _artist_to_genre(conn)
    existing_words = _existing_vocab_words(conn)
    existing_sylls = _existing_cadence_syllables(conn)
    existing_burn = _existing_burn_words(conn)

    songs = _load_corpus()
    if not songs:
        sys.exit(f"No .stats.json files found. Run `python -m tools.corpus_ingest.extract` first.")

    print(f"Loaded {len(songs)} song stat files.")
    matched = sum(1 for s in songs if a2g.get(s["artist_slug"]))
    print(f"  {matched}/{len(songs)} mapped to a genre via songwriter_profiles.")

    print("Rolling up section stats...")
    section_summary = _section_rollups(songs, a2g)
    print(f"  → {len(section_summary)} (genre, section) buckets")

    print("Computing TF-IDF vocab proposals (genre-level)...")
    vocab_proposals = _genre_vocab_candidates(songs, a2g)
    novel_vocab = _diff_vocab(vocab_proposals, existing_words)
    novel_count = sum(len(v) for v in novel_vocab.values())
    print(f"  → {novel_count} NEW words across {len(novel_vocab)} genres")

    print("Computing per-artist distinctive vocab (TF-IDF across artists)...")
    artist_vocab = _artist_vocab_candidates(songs)
    artist_word_count = sum(len(v) for v in artist_vocab.values())
    print(f"  → {artist_word_count} total word candidates across {len(artist_vocab)} artists")

    print("Detecting cross-artist cliché n-grams...")
    ngram_findings = _cliche_ngrams(songs, a2g)
    cliche_alerts = _diff_cliches(ngram_findings, existing_burn)
    print(f"  → {len(cliche_alerts)} novel n-gram clichés (≥3 artists each)")

    print("Diffing cadence templates against DB...")
    cadence_gaps = _diff_cadence(section_summary, existing_sylls)
    print(f"  → {len(cadence_gaps)} observed templates not in cadence_patterns")

    OUT_DIR.joinpath("derived_vocab.json").write_text(
        json.dumps(novel_vocab, indent=2, ensure_ascii=False)
    )
    OUT_DIR.joinpath("derived_artist_vocab.json").write_text(
        json.dumps(artist_vocab, indent=2, ensure_ascii=False)
    )
    OUT_DIR.joinpath("derived_cliches.json").write_text(
        json.dumps(cliche_alerts, indent=2, ensure_ascii=False)
    )
    OUT_DIR.joinpath("derived_cadence.json").write_text(
        json.dumps(section_summary, indent=2, ensure_ascii=False)
    )

    _write_findings(
        section_summary, vocab_proposals, novel_vocab,
        artist_vocab, cliche_alerts, cadence_gaps, len(songs),
    )

    conn.close()
    print(f"\n=== DONE ===")
    print(f"  findings:             {OUT_DIR / 'findings.md'}")
    print(f"  derived_vocab:        {OUT_DIR / 'derived_vocab.json'}")
    print(f"  derived_artist_vocab: {OUT_DIR / 'derived_artist_vocab.json'}")
    print(f"  derived_cliches:      {OUT_DIR / 'derived_cliches.json'}")
    print(f"  derived_cadence:      {OUT_DIR / 'derived_cadence.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
