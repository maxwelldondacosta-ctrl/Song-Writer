"""Fetch lyrics for specific songs from Genius using curated song_lists.yml.

Much faster than search_artist — one targeted search_song() call per title
instead of paginating through an artist's entire discography.

For producers/songwriters, fetches lyrics credited to the original performing
artist and tags the cache record with the songwriter profile slug so the
extract/aggregate pipeline maps it correctly.

Usage:
  # Fetch all artists in song_lists.yml that don't have full caches yet
  python -m tools.corpus_ingest.fetch_by_songs

  # Single artist
  python -m tools.corpus_ingest.fetch_by_songs --artist max-martin

  # Force re-download even if cached
  python -m tools.corpus_ingest.fetch_by_songs --refetch
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = Path(__file__).resolve().parent / "cache"
SONG_LISTS = Path(__file__).resolve().parent / "song_lists.yml"


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "untitled"


def _load_token() -> str:
    load_dotenv(REPO_ROOT / ".env")
    token = os.getenv("GENIUS_TOKEN")
    if not token:
        sys.exit("ERROR: GENIUS_TOKEN not set in .env")
    return token


def _make_genius(token: str):
    import lyricsgenius
    g = lyricsgenius.Genius(
        token,
        timeout=15,
        retries=2,
        sleep_time=0.4,
        remove_section_headers=False,
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)", "(Demo)", "(Acoustic)", "(Instrumental)"],
    )
    if hasattr(g, "verbose"):
        g.verbose = False
    return g


def _fetch_song(g, title: str, artist: str, out_dir: Path, profile_slug: str,
                skip_existing: bool) -> str:
    """Fetch one song. Returns 'fetched' | 'skipped' | 'error'."""
    song_slug = _slug(f"{artist}-{title}")
    out_path = out_dir / f"{song_slug}.json"

    if skip_existing and out_path.exists():
        print(f"    · skip  {title!r} (cached)")
        return "skipped"

    try:
        song = g.search_song(title, artist)
    except Exception as e:
        print(f"    ✗ {title!r}: search error — {e}")
        return "error"

    if song is None or not song.lyrics or len(song.lyrics) < 40:
        print(f"    ✗ {title!r}: not found or empty")
        return "error"

    record = {
        "artist": song.artist,
        "artist_slug": profile_slug,   # map to the songwriter profile, not the performer
        "title": song.title,
        "song_slug": song_slug,
        "url": song.url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "lyrics": song.lyrics,
        # extras for producer entries
        "credited_artist": artist,
        "songwriter_profile": profile_slug,
    }
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"    ✓ {title!r} (by {artist})")
    time.sleep(0.3)
    return "fetched"


def fetch_artist_by_songs(profile_slug: str, entry: dict, token: str,
                          skip_existing: bool) -> dict:
    """Fetch all songs for one artist entry from song_lists.yml."""
    out_dir = CACHE_DIR / profile_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check if already complete
    if skip_existing:
        existing = [f for f in out_dir.iterdir()
                    if f.suffix == ".json" and not f.name.endswith(".stats.json")]
        no_results = out_dir / ".no_results"
        if len(existing) >= 8 or no_results.exists():
            print(f"  [{profile_slug}] skip — {len(existing)} songs already cached")
            return {"fetched": 0, "skipped": len(existing), "errors": 0}

    g = _make_genius(token)
    totals = {"fetched": 0, "skipped": 0, "errors": 0}

    if "songs" in entry:
        # Self-artist: all songs by the same artist
        artist_name = entry["artist"]
        print(f"  [{profile_slug}] {artist_name} — {len(entry['songs'])} songs")
        for title in entry["songs"]:
            result = _fetch_song(g, title, artist_name, out_dir, profile_slug, skip_existing)
            totals[result] += 1

    elif "entries" in entry:
        # Producer/songwriter: each song by a different artist
        print(f"  [{profile_slug}] producer — {len(entry['entries'])} songs")
        for e in entry["entries"]:
            result = _fetch_song(g, e["title"], e["artist"], out_dir, profile_slug, skip_existing)
            totals[result] += 1

    print(f"    → fetched={totals['fetched']} skipped={totals['skipped']} errors={totals['errors']}")
    return totals


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch lyrics by curated song list")
    p.add_argument("--artist", help="Single profile slug (e.g. max-martin)")
    p.add_argument("--refetch", action="store_true", help="Re-download even if cached")
    args = p.parse_args(argv)

    if not SONG_LISTS.exists():
        sys.exit(f"song_lists.yml not found at {SONG_LISTS}")

    song_lists = yaml.safe_load(SONG_LISTS.read_text())
    token = _load_token()
    skip_existing = not args.refetch

    if args.artist:
        if args.artist not in song_lists:
            sys.exit(f"Artist {args.artist!r} not in song_lists.yml")
        entries = {args.artist: song_lists[args.artist]}
    else:
        entries = song_lists

    totals = {"fetched": 0, "skipped": 0, "errors": 0}
    print(f"Fetching {len(entries)} artist(s) from song_lists.yml\n")
    for slug, entry in entries.items():
        r = fetch_artist_by_songs(slug, entry, token, skip_existing)
        for k in totals:
            totals[k] += r[k]

    print(f"\n=== DONE ===")
    print(f"  fetched: {totals['fetched']}")
    print(f"  skipped: {totals['skipped']}")
    print(f"  errors:  {totals['errors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
