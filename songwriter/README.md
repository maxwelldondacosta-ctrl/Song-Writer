# Songwriter

Data layer + build pipeline for the Songwriter app. See `docs/superpowers/specs/2026-04-30-songwriter-app-design.md` for the full spec.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Build the database

```bash
songwriter-build
```

Outputs `data/songwriter.db`.

## Run tests

```bash
pytest -q
```

## Use the songwriting skill

```bash
./start.sh                  # boots the API
claude                      # in another terminal, from this repo root
```

Then in Claude Code:

```
/song new                   # create a song
/song draft                 # draft sections
/song validate              # run validation
/song prompt                # build the Suno prompt
/song export                # finalize and copy prompt
```

See `docs/skill/INVOKE.md` for the full command list.

## Build a distributable Songwriter.app

For the desktop app bundle (real `.app` you can drag to /Applications):

```bash
# First run also compiles ~200 Rust crates — give it 5 min.
cd apps/web && npm run tauri:build
```

Output: `apps/web/src-tauri/target/release/bundle/macos/Songwriter.app`

That .app loads `http://localhost:3737` directly. **It still depends on
`./start.sh` being running** (the .app is a window onto the local servers,
not a self-contained bundle). If the server isn't up, the window shows a
"server not running" page that auto-reloads every 2 seconds — handy because
you can leave the .app open and just run `./start.sh` whenever you want to
work, and the window picks up the live UI automatically.

For the simpler launcher (AppleScript that runs `start.sh` on click), see
`scripts/build-app.sh`.
