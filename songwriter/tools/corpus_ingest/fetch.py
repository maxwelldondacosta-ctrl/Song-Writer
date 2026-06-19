"""Fetch lyrics from Genius for one or many artists.

Usage:
  # Interactive — prompts for artist + count
  python -m tools.corpus_ingest.fetch

  # Single artist
  python -m tools.corpus_ingest.fetch --artist "Frank Ocean" --limit 15

  # All 41 artists already in songwriter_profiles
  python -m tools.corpus_ingest.fetch --all-profiles --limit 10

  # Resume / refresh
  python -m tools.corpus_ingest.fetch --all-profiles --limit 10 --skip-existing

Token: reads GENIUS_TOKEN from `.env` at repo root, or env var.
Cache: tools/corpus_ingest/cache/{artist-slug}/{song-slug}.json
       Each cache file has: {title, artist, url, fetched_at, lyrics, sections?}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = Path(__file__).resolve().parent / "cache"
DB_PATH = REPO_ROOT / "data" / "songwriter.db"


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "untitled"


def _load_token() -> str:
    load_dotenv(REPO_ROOT / ".env")
    token = os.getenv("GENIUS_TOKEN")
    if not token:
        sys.exit(
            "ERROR: GENIUS_TOKEN not set.\n"
            "Add it to .env at repo root:\n"
            f"  echo 'GENIUS_TOKEN=<your-token>' >> {REPO_ROOT / '.env'}\n"
        )
    return token


def _load_profile_artists(db_path: Path) -> list[str]:
    if not db_path.exists():
        sys.exit(f"ERROR: DB not found at {db_path}. Run `songwriter-build` first.")
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT display_name FROM songwriter_profiles ORDER BY display_name"
    ).fetchall()
    db.close()
    # Strip "Jimmy Jam & Terry Lewis" → "Jimmy Jam" (Genius doesn't index duos cleanly)
    names = []
    for r in rows:
        n = r["display_name"]
        if " & " in n:
            n = n.split(" & ")[0]
        names.append(n)
    return names


def _make_genius(token: str):
    """Create a configured lyricsgenius.Genius client."""
    import lyricsgenius

    g = lyricsgenius.Genius(
        token,
        timeout=20,
        retries=2,
        sleep_time=0.6,
        remove_section_headers=False,  # we WANT [Verse 1]/[Chorus] markers
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)", "(Demo)", "(Acoustic)", "(Instrumental)"],
    )
    # The 4.x lib emits a lot of progress noise; the attribute still exists
    # at runtime even though it's no longer a constructor kwarg.
    if hasattr(g, "verbose"):
        g.verbose = False
    return g


def fetch_artist(
    artist_name: str,
    *,
    limit: int,
    token: str,
    skip_existing: bool = True,
    sort: str = "popularity",
) -> dict:
    """Fetch up to `limit` songs for an artist. Returns {fetched, skipped, errors}."""
    artist_slug = _slug(artist_name)
    out_dir = CACHE_DIR / artist_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    g = _make_genius(token)

    # Artist-level skip: skip if we already have songs OR a .no_results marker.
    # The marker is written when Genius returns nothing (producers, name mismatches).
    # Use --refetch to force a fresh pull.
    no_results_marker = out_dir / ".no_results"
    if skip_existing and out_dir.exists():
        existing_songs = [f for f in out_dir.iterdir()
                          if f.suffix == ".json" and not f.name.endswith(".stats.json")]
        if existing_songs or no_results_marker.exists():
            print(f"\n=== {artist_name} ({artist_slug}) — skipping ({len(existing_songs)} songs cached) ===")
            return {"fetched": 0, "skipped": len(existing_songs), "errors": 0}

    print(f"\n=== {artist_name} ({artist_slug}) — fetching up to {limit} songs ===")
    try:
        artist = g.search_artist(artist_name, max_songs=limit, sort=sort, get_full_info=False)
    except Exception as e:
        print(f"  ✗ search_artist failed: {e}")
        return {"fetched": 0, "skipped": 0, "errors": 1}

    if artist is None:
        print(f"  ✗ no artist found on Genius for {artist_name!r}")
        no_results_marker.write_text("no artist found")
        return {"fetched": 0, "skipped": 0, "errors": 1}

    fetched = skipped = errors = 0
    for song in artist.songs[:limit]:
        title = song.title or "untitled"
        song_slug = _slug(title)
        out_path = out_dir / f"{song_slug}.json"

        if skip_existing and out_path.exists():
            skipped += 1
            print(f"  · skip {title} (cached)")
            continue

        if not song.lyrics or len(song.lyrics) < 40:
            print(f"  ✗ {title}: empty/short lyrics, skipping")
            errors += 1
            continue

        record = {
            "artist": artist.name,
            "artist_slug": artist_slug,
            "title": title,
            "song_slug": song_slug,
            "url": song.url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "lyrics": song.lyrics,
        }
        out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
        fetched += 1
        print(f"  ✓ {title}")
        # Be polite to Genius
        time.sleep(0.4)

    if fetched == 0 and skipped == 0:
        no_results_marker.write_text("0 usable songs returned by Genius")
    print(f"  → {fetched} fetched, {skipped} skipped, {errors} errors")
    return {"fetched": fetched, "skipped": skipped, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch lyrics from Genius into local cache")
    p.add_argument("--artist", help="Single artist name (e.g. 'Frank Ocean')")
    p.add_argument("--all-profiles", action="store_true",
                   help="Fetch every artist in songwriter_profiles (41 artists)")
    p.add_argument("--limit", type=int, default=10,
                   help="Max songs per artist (default 10)")
    p.add_argument("--skip-existing", action="store_true", default=True,
                   help="Skip songs already cached (default true)")
    p.add_argument("--refetch", action="store_true",
                   help="Re-download even if cached")
    p.add_argument("--sort", default="popularity",
                   choices=["popularity", "title", "release_date"],
                   help="Genius song-list ordering (default popularity)")
    args = p.parse_args(argv)

    token = _load_token()

    # Interactive prompt if neither --artist nor --all-profiles supplied
    if not args.artist and not args.all_profiles:
        print("Genius lyric corpus ingest")
        print("--------------------------")
        choice = input(
            "1) Single artist\n"
            "2) All 41 artists in songwriter_profiles\n"
            "Choose [1/2]: "
        ).strip()
        if choice == "2":
            args.all_profiles = True
        else:
            args.artist = input("Artist name: ").strip()
            if not args.artist:
                sys.exit("No artist supplied, exiting.")
        try:
            limit = input(f"Max songs per artist [{args.limit}]: ").strip()
            if limit:
                args.limit = int(limit)
        except ValueError:
            print(f"Invalid limit, using default {args.limit}")

    skip_existing = not args.refetch

    totals = {"fetched": 0, "skipped": 0, "errors": 0}
    if args.artist:
        r = fetch_artist(args.artist, limit=args.limit, token=token,
                         skip_existing=skip_existing, sort=args.sort)
        for k, v in r.items():
            totals[k] += v
    else:
        artists = _load_profile_artists(DB_PATH)
        print(f"Fetching {len(artists)} artists at {args.limit} songs each "
              f"(~{len(artists) * args.limit} songs total)\n")
        for i, name in enumerate(artists, 1):
            print(f"\n[{i}/{len(artists)}]")
            r = fetch_artist(name, limit=args.limit, token=token,
                             skip_existing=skip_existing, sort=args.sort)
            for k, v in r.items():
                totals[k] += v

    print(f"\n=== DONE ===")
    print(f"  fetched: {totals['fetched']}")
    print(f"  skipped: {totals['skipped']}")
    print(f"  errors:  {totals['errors']}")
    print(f"  cache:   {CACHE_DIR}")
    return 0 if totals["errors"] == 0 or totals["fetched"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
