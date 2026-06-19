"""Fetch lyrics via lyrics.ovh — free, no API key, no rate limits.

Reads song_lists.yml for the curated artist→song mappings and pulls
lyrics from https://api.lyrics.ovh/v1/{artist}/{title}.

Note: lyrics.ovh returns plain lyrics without section headers ([Verse],
[Chorus], etc.). The extract pipeline treats untagged lyrics as a single
verse, so cadence section-level stats won't be available, but vocab
fingerprinting works correctly.

Usage:
  python -m tools.corpus_ingest.fetch_lyrics_ovh             # all artists
  python -m tools.corpus_ingest.fetch_lyrics_ovh --artist stormzy
  python -m tools.corpus_ingest.fetch_lyrics_ovh --refetch
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
import yaml


REPO_ROOT   = Path(__file__).resolve().parents[2]
CACHE_DIR   = Path(__file__).resolve().parent / "cache"
SONG_LISTS  = Path(__file__).resolve().parent / "song_lists.yml"
API_BASE    = "https://api.lyrics.ovh/v1"
TIMEOUT     = 10
SLEEP       = 0.3   # be polite


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "untitled"


def _fetch_one(artist: str, title: str) -> str | None:
    """Return raw lyrics string or None on miss."""
    url = f"{API_BASE}/{quote(artist)}/{quote(title)}"
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
        lyrics = data.get("lyrics", "").strip()
        return lyrics if len(lyrics) >= 40 else None
    except Exception:
        return None


def _save(out_dir: Path, title: str, artist: str, profile_slug: str,
          lyrics: str) -> None:
    song_slug = _slug(f"{artist}-{title}")
    record = {
        "artist":             artist,
        "artist_slug":        profile_slug,
        "title":              title,
        "song_slug":          song_slug,
        "url":                f"{API_BASE}/{quote(artist)}/{quote(title)}",
        "fetched_at":         datetime.now(timezone.utc).isoformat(),
        "lyrics":             lyrics,
        "credited_artist":    artist,
        "songwriter_profile": profile_slug,
        "source":             "lyrics.ovh",
    }
    path = out_dir / f"{song_slug}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False))


def fetch_artist(profile_slug: str, entry: dict, skip_existing: bool) -> dict:
    out_dir = CACHE_DIR / profile_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = {f.stem for f in out_dir.glob("*.json")
                if not f.name.endswith(".stats.json")}

    if skip_existing and len(existing) >= 8:
        print(f"  [{profile_slug}] skip — {len(existing)} songs already cached")
        return {"fetched": 0, "skipped": len(existing), "errors": 0}

    totals = {"fetched": 0, "skipped": 0, "errors": 0}

    if "songs" in entry:
        # self-artist — all songs by same artist
        artist_name = entry["artist"]
        songs = [(artist_name, t) for t in entry["songs"]]
    else:
        # producer — each song by original credited artist
        songs = [(e["artist"], e["title"]) for e in entry["entries"]]

    label = entry.get("artist", profile_slug)
    print(f"  [{profile_slug}] {label} — {len(songs)} songs")

    for artist, title in songs:
        slug = _slug(f"{artist}-{title}")
        if skip_existing and slug in existing:
            print(f"    · skip  '{title}'")
            totals["skipped"] += 1
            continue

        lyrics = _fetch_one(artist, title)
        if lyrics:
            _save(out_dir, title, artist, profile_slug, lyrics)
            print(f"    ✓ '{title}' (by {artist})")
            totals["fetched"] += 1
        else:
            print(f"    ✗ '{title}' (by {artist}) — not found")
            totals["errors"] += 1

        time.sleep(SLEEP)

    print(f"    → fetched={totals['fetched']} skipped={totals['skipped']} errors={totals['errors']}")
    return totals


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch lyrics via lyrics.ovh")
    p.add_argument("--artist", help="Single profile slug (e.g. stormzy)")
    p.add_argument("--refetch", action="store_true",
                   help="Re-download even if cached")
    args = p.parse_args(argv)

    if not SONG_LISTS.exists():
        sys.exit(f"song_lists.yml not found at {SONG_LISTS}")

    all_entries: dict = yaml.safe_load(SONG_LISTS.read_text())
    skip_existing = not args.refetch

    if args.artist:
        if args.artist not in all_entries:
            sys.exit(f"{args.artist!r} not in song_lists.yml")
        entries = {args.artist: all_entries[args.artist]}
    else:
        entries = all_entries

    print(f"lyrics.ovh fetch — {len(entries)} artist(s)\n")
    totals = {"fetched": 0, "skipped": 0, "errors": 0}

    for slug, entry in entries.items():
        r = fetch_artist(slug, entry, skip_existing)
        for k in totals:
            totals[k] += r[k]

    print(f"\n=== DONE ===")
    print(f"  fetched: {totals['fetched']}")
    print(f"  skipped: {totals['skipped']}")
    print(f"  errors:  {totals['errors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
