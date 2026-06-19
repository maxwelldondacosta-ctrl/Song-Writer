"""Extract per-song stats from cached Genius lyric files.

Reads `tools/corpus_ingest/cache/{artist}/{song}.json`, runs each line
through the existing tokenizer (CMUdict-backed), and writes a sibling
`{song}.stats.json` containing:
  - per-section: kind/label, lines, syllable counts, stress patterns,
    rhyme scheme letters, end-rhyme classes, top content words
  - per-song: title, artist, artist_slug, primary_genre, totals

Usage:
  python -m tools.corpus_ingest.extract              # all cached songs
  python -m tools.corpus_ingest.extract --artist frank-ocean
  python -m tools.corpus_ingest.extract --refresh    # ignore existing .stats.json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from statistics import median

from songwriter.api.validation.tokenizer import tokenize_line


REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = Path(__file__).resolve().parent / "cache"
DB_PATH = REPO_ROOT / "data" / "songwriter.db"


# ---------------- noise stripping ----------------

# Strip these from anywhere in the lyrics body.
_NOISE_PATTERNS = [
    re.compile(r"^\d+\s*Contributors?.*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Translations.*$",         re.MULTILINE | re.IGNORECASE),
    re.compile(r"^.*Lyrics\s*$",            re.MULTILINE),  # song-name lyrics header
    re.compile(r"^You might also like\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^See .*$",                 re.MULTILINE),  # "See Frank Ocean Live"
    re.compile(r"^\d*Embed\s*$",            re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Read More\s*$",           re.MULTILINE | re.IGNORECASE),
]


def _strip_noise(raw: str) -> str:
    out = raw
    for pat in _NOISE_PATTERNS:
        out = pat.sub("", out)
    # Genius sometimes glues "Embed" onto last line — strip trailing Embed.
    out = re.sub(r"\s*\d*Embed\s*$", "", out, flags=re.IGNORECASE)
    return out


# ---------------- section parsing ----------------

_HEADER_RE = re.compile(r"^\[([^\]]+)\]\s*$")


def _classify_kind(header: str) -> str:
    h = header.lower()
    if "pre" in h and "chorus" in h:
        return "pre-chorus"
    if "chorus" in h or "hook" in h or "refrain" in h:
        return "chorus"
    if "verse" in h:
        return "verse"
    if "bridge" in h:
        return "bridge"
    if "intro" in h:
        return "intro"
    if "outro" in h:
        return "outro"
    if "drop" in h:
        return "drop"
    if "interlude" in h:
        return "interlude"
    if "post" in h and "chorus" in h:
        return "post-chorus"
    if h.startswith("part"):
        return "part-marker"  # nested; lines below it usually under another header
    return "other"


def _parse_sections(text: str) -> list[dict]:
    """Split lyric text by [Header] blocks into list of {kind, label, lines}."""
    sections: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _HEADER_RE.match(line)
        if m:
            label = m.group(1).strip()
            kind = _classify_kind(label)
            if kind == "part-marker":
                # Skip section-of-section markers; let the next [Verse]/[Chorus] win
                continue
            if current and current["lines"]:
                sections.append(current)
            current = {"kind": kind, "label": label, "lines": []}
            continue
        # body line
        if current is None:
            # untagged opening — treat as "verse" until we see a header
            current = {"kind": "verse", "label": "Verse 1", "lines": []}
        # Strip parenthetical ad-libs at line ends (preserve within-line ones)
        # Drop "(x2)" / "(repeat)" markers
        line = re.sub(r"\s*\(x\d+\)\s*$", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\s*\(repeat\)\s*$", "", line, flags=re.IGNORECASE)
        if line:
            current["lines"].append(line)
    if current and current["lines"]:
        sections.append(current)
    return sections


# ---------------- stopwords for top-content-word extraction ----------------

_STOP = {
    # function words
    "the", "a", "an", "and", "but", "or", "so", "if", "as", "of", "to", "in",
    "on", "at", "for", "with", "from", "by", "is", "are", "was", "were", "be",
    "been", "being", "am", "do", "does", "did", "have", "has", "had", "having",
    "i", "me", "my", "mine", "myself", "you", "your", "yours", "yourself",
    "he", "him", "his", "himself", "she", "her", "hers", "herself", "it",
    "its", "itself", "we", "us", "our", "ours", "ourselves", "they", "them",
    "their", "theirs", "themselves", "this", "that", "these", "those",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "not", "only", "own", "same", "than", "too", "very",
    "can", "will", "would", "should", "could", "may", "might", "must",
    "shall", "ought", "now", "just", "yeah", "yo", "uh", "oh", "ah", "ay",
    "ayy", "ah", "huh", "hey", "okay", "ok", "like", "well", "really",
    "got", "get", "go", "come", "make", "made", "take", "give", "say",
    "said", "see", "know", "want", "need", "think", "feel", "let",
    # contractions stripped
    "don", "won", "ain", "didn", "doesn", "isn", "wasn", "couldn", "wouldn",
    "shouldn", "haven", "hasn", "hadn", "ll", "re", "ve", "s", "t", "d", "m",
    # generic emotion clichés we want to catch — keep these out of top-words
    "love", "heart", "soul", "pain", "sad", "happy", "hate",
}


def _content_words(line: str) -> list[str]:
    raw = re.findall(r"[a-z']+", line.lower())
    return [w.strip("'") for w in raw if w.strip("'") and w.strip("'") not in _STOP]


# ---------------- per-section stats ----------------

def _section_stats(section: dict, conn: sqlite3.Connection) -> dict:
    lines = section["lines"]
    syll_per_line: list[int] = []
    stress_per_line: list[str] = []
    end_rhyme_classes: list[str] = []  # rhyme class of last known word per line
    word_counter: Counter[str] = Counter()

    for line in lines:
        toks = tokenize_line(line, conn)
        known = [t for t in toks if not t.unknown]
        syll = sum(t.syllables for t in known)
        stress = "".join(t.stress_pattern for t in known)
        # last known word's rhyme class
        end_rc = ""
        for t in reversed(known):
            if t.rhyme_class:
                end_rc = t.rhyme_class
                break
        syll_per_line.append(syll)
        stress_per_line.append(stress)
        end_rhyme_classes.append(end_rc)
        for w in _content_words(line):
            word_counter[w] += 1

    # Build a rhyme scheme like "AABB" / "ABAB" — letters assigned in order.
    scheme: list[str] = []
    rc_to_letter: dict[str, str] = {}
    next_letter = ord("A")
    for rc in end_rhyme_classes:
        if not rc:
            scheme.append("-")
            continue
        if rc not in rc_to_letter:
            if next_letter <= ord("Z"):
                rc_to_letter[rc] = chr(next_letter)
                next_letter += 1
            else:
                rc_to_letter[rc] = "?"
        scheme.append(rc_to_letter[rc])
    scheme_str = "".join(scheme)

    syll_clean = [s for s in syll_per_line if s > 0]
    stats = {
        "kind":          section["kind"],
        "label":         section["label"],
        "line_count":    len(lines),
        "syll_min":      min(syll_clean) if syll_clean else 0,
        "syll_max":      max(syll_clean) if syll_clean else 0,
        "syll_median":   int(median(syll_clean)) if syll_clean else 0,
        "syll_per_line": syll_per_line,
        "stress_per_line": stress_per_line,
        "rhyme_scheme":  scheme_str,
        "end_rhyme_classes": end_rhyme_classes,
        "top_words":     word_counter.most_common(15),
    }
    return stats


# ---------------- per-song extraction ----------------

def extract_song(song_record: dict, conn: sqlite3.Connection) -> dict:
    """Process one cached lyric record into a stats dict."""
    cleaned = _strip_noise(song_record["lyrics"])
    sections = _parse_sections(cleaned)
    section_stats = [_section_stats(s, conn) for s in sections]

    # roll up
    all_top_words: Counter[str] = Counter()
    for s in section_stats:
        for w, n in s["top_words"]:
            all_top_words[w] += n

    return {
        "artist":      song_record["artist"],
        "artist_slug": song_record["artist_slug"],
        "title":       song_record["title"],
        "song_slug":   song_record["song_slug"],
        "url":         song_record.get("url"),
        "section_count": len(section_stats),
        "sections":    section_stats,
        "top_words":   all_top_words.most_common(30),
    }


# ---------------- driver ----------------

def _open_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit(f"ERROR: DB not found at {DB_PATH}. Run songwriter-build first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Extract stats from cached lyric files")
    p.add_argument("--artist", help="Artist slug to limit to (e.g. frank-ocean)")
    p.add_argument("--refresh", action="store_true",
                   help="Re-extract even if .stats.json exists")
    args = p.parse_args(argv)

    conn = _open_db()

    artist_dirs = (
        [CACHE_DIR / args.artist] if args.artist
        else [d for d in CACHE_DIR.iterdir() if d.is_dir()]
    )
    artist_dirs = [d for d in artist_dirs if d.exists()]
    if not artist_dirs:
        sys.exit(f"No cached artist directories found in {CACHE_DIR}")

    total_processed = total_skipped = total_errors = 0
    for adir in sorted(artist_dirs):
        json_files = sorted(p for p in adir.glob("*.json") if not p.name.endswith(".stats.json"))
        if not json_files:
            continue
        print(f"\n=== {adir.name} ({len(json_files)} songs) ===")
        for jf in json_files:
            stats_path = jf.with_suffix(".stats.json")
            if stats_path.exists() and not args.refresh:
                total_skipped += 1
                continue
            try:
                record = json.loads(jf.read_text())
                stats = extract_song(record, conn)
                stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False))
                total_processed += 1
                print(f"  ✓ {record['title']}: {stats['section_count']} sections, "
                      f"{sum(s['line_count'] for s in stats['sections'])} lines")
            except Exception as e:
                total_errors += 1
                print(f"  ✗ {jf.name}: {e}")

    conn.close()
    print(f"\n=== DONE === processed={total_processed} skipped={total_skipped} errors={total_errors}")
    return 0 if total_errors == 0 or total_processed > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
