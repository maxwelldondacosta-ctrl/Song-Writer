# Songwriter FastAPI Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend that serves the Next.js web UI and Claude Code skill from the SQLite DB shipped by the data-layer plan, runs all 5 validation engines (4 deterministic + 1 LLM-judged), broadcasts live JSON updates to the UI over WebSocket, and exposes an auto-LLM descriptor cache pipeline. All LLM work routes through `claude --print` subprocess (zero API cost; user's MAX quota covers it).

**Architecture:** A new `src/songwriter/api/` package alongside the existing `src/songwriter/seeds/` package. FastAPI app factory in `api/main.py`. DB access via a thin dependency that opens a row-factory connection per request and closes it after. Song JSON files live at `~/Songwriter/songs/<slug>.json`; the API both reads/writes them and a `watchdog`-based file watcher broadcasts external changes (skill writes) over WebSocket. Validation engines split into a `validation/` subpackage — each rule is its own module with a `check(line, ctx)` or `check(section, ctx)` interface returning `pass | warn | fail` plus structured findings.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, watchdog, pydantic v2, pytest, pytest-asyncio, httpx (test client). Subprocess invocation of `claude --print` for LLM-judged work.

**Scope boundary:** This plan ships the API surface only. It does not ship the Claude Code skill (separate sub-plan) or the Next.js web UI (separate sub-plan). The song JSON shape defined here in `schemas.py` is the cross-plan contract.

**Sister plans:**
- ✅ `2026-04-30-songwriter-data-layer.md` — done, ships `data/songwriter.db` this plan consumes
- ⏳ `2026-MM-DD-songwriter-skill.md` — Claude Code `/song` skill, calls these endpoints
- ⏳ `2026-MM-DD-songwriter-web-ui.md` — Next.js UI, consumes endpoints + WebSocket

**Decisions baked into this plan:**
- LLM calls shell out to `claude --print "<prompt>"` and parse stdout (uses CC subscription, $0 cost). A wrapper module `api/llm.py` hides the subprocess detail.
- Validation engines: 4 deterministic (Singability, Cadence, Phonetic Texture, Rhyme-Cadence) run inline on every `POST /validate`. The Story / Continuity / Consistency engine is LLM-judged and runs on the same endpoint but is throttled (cached per-section signature so it doesn't burn quota on every save).
- Song JSON file is the source of truth. The API reads it on every GET, writes atomically (write to temp, rename) on every mutation. Last-writer-wins; no DB-side song state.
- WebSocket broadcasts on file change. When the API itself writes a song JSON, it broadcasts directly (no round-trip through the watcher) so the watcher only needs to handle external (skill) writes.
- Descriptor cache: a GET on a missing descriptor triggers auto-LLM generation, saves the result, and returns it. Token-bias scrub applies to the generated text. `quality_state` defaults to `unverified`.

---

## File Structure

```
songwriter/
├── pyproject.toml                 # extended with FastAPI deps
├── start.sh                       # boots uvicorn + tail-friendly logs
├── songs/                         # default song JSON dir (gitignored)
└── src/songwriter/
    ├── seeds/                     # existing — DB build pipeline
    └── api/                       # NEW
        ├── __init__.py
        ├── main.py                # FastAPI app factory; CORS for the Next.js dev server
        ├── settings.py            # Pydantic Settings: DB path, songs dir, log level
        ├── deps.py                # dependency-injected helpers (DB conn, songs dir)
        ├── llm.py                 # claude --print subprocess wrapper
        ├── schemas.py             # Pydantic v2 models: Song, Section, Validation, etc.
        ├── songs_io.py            # song-file CRUD (slug → path, atomic write, list)
        ├── ws.py                  # ConnectionManager (per-song-slug broadcast)
        ├── watcher.py             # watchdog handler that pushes to ws
        ├── routes/
        │   ├── __init__.py
        │   ├── lookups.py         # genres, sub-genres, cadence, vocab, rhymes, words, burn list
        │   ├── production.py      # production_fingerprints, emotion_tempo
        │   ├── songwriters.py     # songwriter profiles
        │   ├── descriptors.py     # artist descriptor cache + auto-LLM
        │   ├── songs.py           # /songs CRUD + websocket
        │   └── validate.py        # validation orchestrator endpoint
        └── validation/
            ├── __init__.py
            ├── tokenizer.py       # line → tokens, words DB resolver
            ├── singability.py     # deterministic
            ├── cadence.py         # deterministic
            ├── phonetic_texture.py # deterministic
            ├── rhyme_cadence.py   # deterministic
            ├── story_sentence.py  # LLM-judged via llm.py
            └── orchestrator.py    # runs all engines, writes results into song JSON
└── tests/
    ├── api/
    │   ├── conftest.py            # FastAPI TestClient fixture, fresh DB per test
    │   ├── test_lookups.py
    │   ├── test_production.py
    │   ├── test_songwriters.py
    │   ├── test_descriptors.py
    │   ├── test_songs_crud.py
    │   ├── test_validate.py
    │   ├── test_ws.py
    │   ├── test_watcher.py
    │   └── test_integration.py    # end-to-end: create song, edit section, run validate, see WS event
    └── validation/
        ├── conftest.py            # validation context fixtures
        ├── test_tokenizer.py
        ├── test_singability.py
        ├── test_cadence.py
        ├── test_phonetic_texture.py
        ├── test_rhyme_cadence.py
        └── test_story_sentence.py
```

---

## Conventions

- TDD: failing test → implementation → passing test → commit. One commit per task. **No committing failing tests.**
- pytest collects from `tests/` (already configured). New tests live under `tests/api/` and `tests/validation/`.
- Async tests use `pytest-asyncio` mode `auto` (configured in pyproject).
- Commit message format: `feat(api): <subject>` for endpoints, `feat(validation): <subject>` for rule engines, `chore(api): <subject>` for plumbing.
- The API never imports `anthropic`. All AI calls flow through `api/llm.py`.

---

## Task 1: FastAPI scaffolding + app factory + healthcheck

**Files:**
- Modify: `songwriter/pyproject.toml` (add deps)
- Create: `src/songwriter/api/__init__.py`
- Create: `src/songwriter/api/settings.py`
- Create: `src/songwriter/api/main.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/conftest.py`
- Create: `tests/api/test_main.py`

- [ ] **Step 1: Add deps to `pyproject.toml`**

In `[project] dependencies` add:

```toml
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "watchdog>=4.0",
  "pydantic-settings>=2.0",
```

In `[project.optional-dependencies] dev` add:

```toml
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
```

In `[tool.pytest.ini_options]` add:

```toml
asyncio_mode = "auto"
```

Reinstall: `pip install -e ".[dev]"`.

- [ ] **Step 2: Write `settings.py`**

File: `src/songwriter/api/settings.py`

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from songwriter.seeds import DB_PATH as DEFAULT_DB_PATH


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SONGWRITER_", env_file=".env", extra="ignore")

    db_path: Path = DEFAULT_DB_PATH
    songs_dir: Path = Path.home() / "Songwriter" / "songs"
    cors_origins: list[str] = ["http://localhost:3000"]
    claude_cli: str = "claude"  # path to Claude Code binary
    llm_timeout_s: int = 60


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Write `main.py`**

File: `src/songwriter/api/main.py`

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from songwriter.api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.songs_dir.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(title="Songwriter API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "db": str(settings.db_path), "songs_dir": str(settings.songs_dir)}

    app.state.settings = settings
    return app


app = create_app()
```

- [ ] **Step 4: Write `tests/api/conftest.py`**

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from songwriter.api.main import create_app
from songwriter.api.settings import Settings
from songwriter.seeds import db as db_module
from songwriter.seeds.build import run as build_run


@pytest.fixture(scope="session")
def built_db(tmp_path_factory):
    """Build a real DB once per test session using the small CMUdict fixture."""
    target = tmp_path_factory.mktemp("data") / "songwriter.db"
    cache_dir = tmp_path_factory.mktemp("cache")
    fixture = Path(__file__).parent.parent / "fixtures" / "cmudict_vocab_words.txt"
    (cache_dir / "cmudict.dict").write_text(fixture.read_text())
    build_run(db_path=target, cache_dir=cache_dir)
    return target


@pytest.fixture
def settings(built_db, tmp_path) -> Settings:
    return Settings(db_path=built_db, songs_dir=tmp_path / "songs")


@pytest.fixture
def client(settings) -> TestClient:
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 5: Write `tests/api/test_main.py`**

```python
def test_healthz_returns_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"].endswith("songwriter.db")
```

- [ ] **Step 6: Run, verify PASS**

```bash
pytest tests/api/test_main.py -v
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/songwriter/api tests/api
git commit -m "feat(api): scaffold FastAPI app + healthcheck"
```

---

## Task 2: LLM bridge — `claude --print` subprocess wrapper

**Files:**
- Create: `src/songwriter/api/llm.py`
- Create: `tests/api/test_llm.py`

- [ ] **Step 1: Write the failing test**

File: `tests/api/test_llm.py`

```python
import json
from unittest.mock import patch

import pytest

from songwriter.api.llm import LLMError, ask_claude, ask_claude_json


def test_ask_claude_returns_stdout(settings):
    fake_proc = type("P", (), {"returncode": 0, "stdout": "hello world\n", "stderr": ""})()
    with patch("songwriter.api.llm.subprocess.run", return_value=fake_proc) as m:
        out = ask_claude("say hello", settings=settings)
    assert out == "hello world"
    args, kwargs = m.call_args
    assert args[0][:2] == [settings.claude_cli, "--print"]


def test_ask_claude_raises_on_nonzero_exit(settings):
    fake_proc = type("P", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()
    with patch("songwriter.api.llm.subprocess.run", return_value=fake_proc):
        with pytest.raises(LLMError) as exc:
            ask_claude("fail", settings=settings)
    assert "boom" in str(exc.value)


def test_ask_claude_json_extracts_first_json_block(settings):
    payload = 'Here is the result:\n```json\n{"verdict":"pass","note":"ok"}\n```\nthat is all'
    fake_proc = type("P", (), {"returncode": 0, "stdout": payload, "stderr": ""})()
    with patch("songwriter.api.llm.subprocess.run", return_value=fake_proc):
        out = ask_claude_json("classify this", settings=settings)
    assert out == {"verdict": "pass", "note": "ok"}


def test_ask_claude_json_fallback_to_bare_json(settings):
    fake_proc = type("P", (), {"returncode": 0, "stdout": '{"x": 42}\n', "stderr": ""})()
    with patch("songwriter.api.llm.subprocess.run", return_value=fake_proc):
        out = ask_claude_json("emit json", settings=settings)
    assert out == {"x": 42}
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement `llm.py`**

File: `src/songwriter/api/llm.py`

```python
"""Bridge to Claude Code as an LLM provider.

Shells out to `claude --print "<prompt>"` and reads stdout. This uses the user's
Claude Code subscription (zero billed-API cost). The wrapper is intentionally thin
— callers should prepare the prompt themselves and parse free-form output, or use
`ask_claude_json` for prompts that promise structured JSON.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from songwriter.api.settings import Settings, get_settings


class LLMError(RuntimeError):
    pass


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def ask_claude(prompt: str, *, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    cmd = [settings.claude_cli, "--print", prompt]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=settings.llm_timeout_s,
    )
    if proc.returncode != 0:
        raise LLMError(f"claude --print failed (exit {proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


def ask_claude_json(prompt: str, *, settings: Settings | None = None) -> Any:
    """Same as ask_claude, but extracts a JSON object from the response.

    Tries fenced ```json blocks first, then falls back to parsing the whole stdout.
    """
    raw = ask_claude(prompt, settings=settings)
    m = _JSON_FENCE.search(raw)
    candidate = m.group(1) if m else raw
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise LLMError(f"could not parse JSON from claude output: {e}\noutput was:\n{raw}") from e
```

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/api/llm.py tests/api/test_llm.py
git commit -m "feat(api): add claude --print subprocess LLM bridge"
```

---

## Task 3: DB connection dependency

**Files:**
- Create: `src/songwriter/api/deps.py`
- Create: `tests/api/test_deps.py`

- [ ] **Step 1: Write failing test**

File: `tests/api/test_deps.py`

```python
from songwriter.api.deps import get_db


def test_get_db_yields_connection_and_closes(settings):
    gen = get_db(settings)
    conn = next(gen)
    row = conn.execute("SELECT COUNT(*) AS c FROM genres").fetchone()
    assert row["c"] == 12
    # exhaust the generator → closes the connection
    gen.close()


def test_get_db_uses_settings_db_path(settings):
    gen = get_db(settings)
    conn = next(gen)
    assert conn.execute("SELECT 1").fetchone()[0] == 1
    gen.close()
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement `deps.py`**

File: `src/songwriter/api/deps.py`

```python
from collections.abc import Generator
import sqlite3

from fastapi import Depends, Request

from songwriter.api.settings import Settings
from songwriter.seeds import db as db_module


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(settings: Settings = Depends(get_settings)) -> Generator[sqlite3.Connection, None, None]:
    conn = db_module.connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
```

Note: tests call `get_db(settings)` directly (bypassing FastAPI's `Depends`); the function works in both contexts because settings is a regular argument.

- [ ] **Step 4: Run, verify PASS. Commit**

```bash
git add src/songwriter/api/deps.py tests/api/test_deps.py
git commit -m "feat(api): add DB connection dependency"
```

---

## Task 4: Lookup endpoints — genres, sub-genres, cadence, vocab, words, rhymes, burn list

**Files:**
- Create: `src/songwriter/api/routes/__init__.py`
- Create: `src/songwriter/api/routes/lookups.py`
- Modify: `src/songwriter/api/main.py` (register router)
- Create: `tests/api/test_lookups.py`

This task ships the cluster of read-only lookup endpoints that the UI/skill use most often. All return JSON arrays of dicts; no auth.

- [ ] **Step 1: Write the failing test**

File: `tests/api/test_lookups.py`

```python
def test_list_genres(client):
    resp = client.get("/genres")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 12
    slugs = {g["slug"] for g in data}
    assert {"pop", "rnb"} <= slugs


def test_get_genre_with_sub_genres(client):
    resp = client.get("/genres/pop")
    assert resp.status_code == 200
    g = resp.json()
    assert g["slug"] == "pop"
    sub_slugs = {s["slug"] for s in g["sub_genres"]}
    assert {"dance-pop", "synth-pop"} <= sub_slugs


def test_get_unknown_genre_404(client):
    assert client.get("/genres/nonexistent").status_code == 404


def test_list_cadence_patterns(client):
    resp = client.get("/cadence-patterns")
    assert resp.status_code == 200
    assert len(resp.json()) == 10


def test_get_vocab_bank_words(client):
    resp = client.get("/vocab-banks/pop.confession/words")
    assert resp.status_code == 200
    words = {w["word"] for w in resp.json()}
    assert "voicemail" in words


def test_get_word_phonetics(client):
    resp = client.get("/words/love")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ipa"] == "lʌv"
    assert body["rhyme_class"] == "AH-V"


def test_get_word_404(client):
    assert client.get("/words/zxqvbnm").status_code == 404


def test_rhymes_for_word_returns_same_class(client):
    resp = client.get("/rhymes?word=love&limit=20")
    assert resp.status_code == 200
    out = resp.json()
    assert out["rhyme_class"] == "AH-V"
    rhymes = {w["word"] for w in out["words"]}
    assert "above" in rhymes
    assert "love" not in rhymes  # query word excluded


def test_burn_list(client):
    resp = client.get("/burn-list")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 50
    words = {b["word"] for b in data}
    assert "neon" in words
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement `routes/lookups.py`**

File: `src/songwriter/api/routes/lookups.py`

```python
import json
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db


router = APIRouter()


def _row_to_dict(row: sqlite3.Row, json_cols: tuple[str, ...] = ()) -> dict:
    d = dict(row)
    for c in json_cols:
        if c in d and isinstance(d[c], str):
            try:
                d[c] = json.loads(d[c])
            except (TypeError, json.JSONDecodeError):
                pass
    return d


@router.get("/genres")
def list_genres(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM genres ORDER BY name").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/genres/{slug}")
def get_genre(slug: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    row = db.execute("SELECT * FROM genres WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise HTTPException(404, f"genre {slug!r} not found")
    out = _row_to_dict(row)
    sub_rows = db.execute(
        "SELECT * FROM sub_genres WHERE genre_id = ? ORDER BY name", (out["id"],)
    ).fetchall()
    out["sub_genres"] = [_row_to_dict(r) for r in sub_rows]
    return out


@router.get("/sub-genres")
def list_sub_genres(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute(
        """
        SELECT sg.*, g.slug AS parent_slug
        FROM sub_genres sg JOIN genres g ON g.id = sg.genre_id
        ORDER BY g.name, sg.name
        """
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/cadence-patterns")
def list_cadence_patterns(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM cadence_patterns ORDER BY slug").fetchall()
    return [_row_to_dict(r, ("typical_genres", "example_lines", "rhyme_compatibility")) for r in rows]


@router.get("/vocab-banks")
def list_vocab_banks(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM vocab_banks ORDER BY slug").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/vocab-banks/{slug}/words")
def get_vocab_bank_words(slug: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    bank = db.execute("SELECT id FROM vocab_banks WHERE slug = ?", (slug,)).fetchone()
    if not bank:
        raise HTTPException(404, f"vocab bank {slug!r} not found")
    rows = db.execute(
        """
        SELECT w.word, w.ipa, w.syllables, w.stress_pattern, w.rhyme_class,
               w.vowel_shape, w.first_syllable_attack, w.consonant_density,
               vbw.emotional_weight, vbw.imagery_class, vbw.cliche_flag, vbw.ai_bias_flag
        FROM vocab_bank_words vbw
        JOIN words w ON w.id = vbw.word_id
        WHERE vbw.bank_id = ?
        ORDER BY w.word
        """,
        (bank["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/words/{word}")
def get_word(word: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    row = db.execute(
        "SELECT * FROM words WHERE word = ? AND language = 'en'",
        (word.lower(),),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"word {word!r} not in dictionary")
    return dict(row)


@router.get("/rhymes")
def get_rhymes(
    word: str,
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    limit: int = Query(50, ge=1, le=500),
):
    base = db.execute(
        "SELECT rhyme_class FROM words WHERE word = ? AND language = 'en'",
        (word.lower(),),
    ).fetchone()
    if not base or not base["rhyme_class"]:
        raise HTTPException(404, f"no rhyme data for {word!r}")
    rc = base["rhyme_class"]
    rows = db.execute(
        """
        SELECT word, ipa, syllables, stress_pattern, vowel_shape,
               first_syllable_attack, consonant_density
        FROM words
        WHERE rhyme_class = ? AND language = 'en' AND word != ?
        ORDER BY syllables, word
        LIMIT ?
        """,
        (rc, word.lower(), limit),
    ).fetchall()
    return {"rhyme_class": rc, "words": [dict(r) for r in rows]}


@router.get("/burn-list")
def list_burn_list(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM suno_burn_list ORDER BY severity DESC, word").fetchall()
    return [_row_to_dict(r, ("alternatives",)) for r in rows]
```

- [ ] **Step 4: Wire the router into `main.py`**

In `src/songwriter/api/main.py`, after the healthz endpoint:

```python
from songwriter.api.routes import lookups
app.include_router(lookups.router)
```

- [ ] **Step 5: Run tests, verify PASS. Commit**

```bash
git add src/songwriter/api/main.py src/songwriter/api/routes tests/api/test_lookups.py
git commit -m "feat(api): add lookup endpoints (genres, vocab, words, rhymes, burn list)"
```

---

## Task 5: Production fingerprints + emotion-tempo + structure templates endpoints

**Files:**
- Create: `src/songwriter/api/routes/production.py`
- Modify: `src/songwriter/api/main.py`
- Create: `tests/api/test_production.py`

- [ ] **Step 1: Write failing test**

File: `tests/api/test_production.py`

```python
def test_get_production_fingerprint(client):
    resp = client.get("/production-fingerprints/alt-rnb")
    assert resp.status_code == 200
    body = resp.json()
    negs = body["negative_descriptors"]
    assert any("bright" in n.lower() or "EDM" in n for n in negs)


def test_get_production_fingerprint_404(client):
    assert client.get("/production-fingerprints/nonexistent").status_code == 404


def test_get_emotion_tempo(client):
    resp = client.get("/emotion-tempo?emotion=surrender&sub_genre=alt-rnb")
    assert resp.status_code == 200
    body = resp.json()
    assert 60 <= body["bpm_min"] <= body["bpm_max"] <= 100
    assert "EDM-build" in body["anti_prompts"]


def test_get_emotion_tempo_404(client):
    assert client.get("/emotion-tempo?emotion=apathy&sub_genre=alt-rnb").status_code == 404


def test_list_structure_templates(client):
    resp = client.get("/structure-templates")
    assert resp.status_code == 200
    slugs = {t["slug"] for t in resp.json()}
    assert "pop.standard" in slugs
    assert "rnb.intimate-confession" in slugs
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement `routes/production.py`**

```python
import json
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db


router = APIRouter()


def _resolve_sub_genre_id(db: sqlite3.Connection, dotted: str) -> int | None:
    if "." in dotted:
        g_slug, sg_slug = dotted.split(".", 1)
        row = db.execute(
            """
            SELECT sg.id FROM sub_genres sg JOIN genres g ON g.id = sg.genre_id
            WHERE g.slug = ? AND sg.slug = ?
            """,
            (g_slug, sg_slug),
        ).fetchone()
    else:
        row = db.execute("SELECT id FROM sub_genres WHERE slug = ?", (dotted,)).fetchone()
    return row["id"] if row else None


_FP_JSON_COLS = ("instrumentation", "vocal_style", "mix_attributes",
                 "positive_descriptors", "negative_descriptors")


@router.get("/production-fingerprints/{sub_genre}")
def get_production_fingerprint(sub_genre: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    sg_id = _resolve_sub_genre_id(db, sub_genre)
    if sg_id is None:
        raise HTTPException(404, f"sub-genre {sub_genre!r} not found")
    row = db.execute(
        "SELECT * FROM production_fingerprints WHERE sub_genre_id = ?", (sg_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, f"no fingerprint for {sub_genre!r}")
    out = dict(row)
    for c in _FP_JSON_COLS:
        out[c] = json.loads(out[c]) if out.get(c) else None
    return out


@router.get("/emotion-tempo")
def get_emotion_tempo(
    emotion: str,
    sub_genre: str,
    db: Annotated[sqlite3.Connection, Depends(get_db)],
):
    sg_id = _resolve_sub_genre_id(db, sub_genre)
    if sg_id is None:
        raise HTTPException(404, f"sub-genre {sub_genre!r} not found")
    row = db.execute(
        "SELECT * FROM emotion_tempo_map WHERE emotion = ? AND sub_genre_id = ?",
        (emotion, sg_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"no emotion-tempo entry for {emotion!r} × {sub_genre!r}")
    out = dict(row)
    out["energy_curve"] = json.loads(out["energy_curve"]) if out["energy_curve"] else []
    out["anti_prompts"] = json.loads(out["anti_prompts"]) if out["anti_prompts"] else []
    return out


@router.get("/structure-templates")
def list_structure_templates(db: Annotated[sqlite3.Connection, Depends(get_db)]):
    rows = db.execute("SELECT * FROM structure_templates ORDER BY slug").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["sections"] = json.loads(d["sections"]) if d["sections"] else []
        d["genre_compatibility"] = json.loads(d["genre_compatibility"]) if d["genre_compatibility"] else []
        out.append(d)
    return out
```

- [ ] **Step 4: Register router in `main.py`** (`from .routes import production; app.include_router(production.router)`).

- [ ] **Step 5: Run, verify PASS. Commit**

```bash
git add src/songwriter/api/main.py src/songwriter/api/routes/production.py tests/api/test_production.py
git commit -m "feat(api): add production fingerprint, emotion-tempo, structure template endpoints"
```

---

## Task 6: Songwriter profile endpoints

**Files:**
- Create: `src/songwriter/api/routes/songwriters.py`
- Modify: `src/songwriter/api/main.py`
- Create: `tests/api/test_songwriters.py`

- [ ] **Step 1: Write failing test**

```python
def test_list_songwriter_profiles(client):
    resp = client.get("/songwriter-profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10
    slugs = {p["slug"] for p in data}
    assert {"frank-ocean", "diane-warren"} <= slugs


def test_filter_by_genre(client):
    resp = client.get("/songwriter-profiles?genre=rnb")
    assert resp.status_code == 200
    slugs = {p["slug"] for p in resp.json()}
    assert "frank-ocean" in slugs
    assert "diane-warren" not in slugs


def test_filter_by_role(client):
    resp = client.get("/songwriter-profiles?role=pure-songwriter")
    assert resp.status_code == 200
    data = resp.json()
    assert all(p["role"] == "pure-songwriter" for p in data)
    assert {p["slug"] for p in data} == {"diane-warren"}


def test_get_one_profile(client):
    resp = client.get("/songwriter-profiles/frank-ocean")
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "self-writing-artist"
    assert isinstance(body["craft_signature"], list)
    assert "adoption_prompt" in body and len(body["adoption_prompt"]) > 50


def test_unknown_profile_404(client):
    assert client.get("/songwriter-profiles/nope").status_code == 404
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

```python
import json
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db


router = APIRouter()


_JSON_COLS = ("sub_genres", "notable_credits", "craft_signature", "personality_traits",
              "writing_style", "preferred_cadences", "vocab_fingerprint",
              "phonetic_fingerprint", "structure_preferences", "reference_tracks")


def _hydrate(row: sqlite3.Row) -> dict:
    d = dict(row)
    for c in _JSON_COLS:
        d[c] = json.loads(d[c]) if d.get(c) else None
    return d


@router.get("/songwriter-profiles")
def list_profiles(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    genre: str | None = Query(None),
    role: str | None = Query(None),
):
    sql = """
        SELECT sp.*, g.slug AS primary_genre_slug
        FROM songwriter_profiles sp
        LEFT JOIN genres g ON g.id = sp.primary_genre_id
    """
    where = []
    args: list = []
    if genre:
        where.append("g.slug = ?")
        args.append(genre)
    if role:
        where.append("sp.role = ?")
        args.append(role)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY sp.display_name"
    rows = db.execute(sql, args).fetchall()
    return [_hydrate(r) for r in rows]


@router.get("/songwriter-profiles/{slug}")
def get_profile(slug: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    row = db.execute(
        """
        SELECT sp.*, g.slug AS primary_genre_slug
        FROM songwriter_profiles sp
        LEFT JOIN genres g ON g.id = sp.primary_genre_id
        WHERE sp.slug = ?
        """,
        (slug,),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"songwriter profile {slug!r} not found")
    return _hydrate(row)
```

- [ ] **Step 4: Register router. Run, verify PASS. Commit**

```bash
git add src/songwriter/api/main.py src/songwriter/api/routes/songwriters.py tests/api/test_songwriters.py
git commit -m "feat(api): add songwriter profile endpoints"
```

---

## Task 7: Sonic descriptor cache + auto-LLM-on-miss

**Files:**
- Create: `src/songwriter/api/routes/descriptors.py`
- Modify: `src/songwriter/api/main.py`
- Create: `tests/api/test_descriptors.py`

The descriptor cache pipeline (per spec):
1. Normalize the requested name.
2. HIT (any quality_state) → return + bump `use_count` + update `last_used_at`.
3. MISS → call `llm.ask_claude_json` with a strict prompt that returns `{descriptor_short, descriptor_long, vocal_attributes, production_attrs, genre_context}`. Token-bias scrub. Insert with `source='auto-llm'`, `quality_state='unverified'`. Return.

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import patch


def test_get_descriptor_hit_increments_use_count(client, settings):
    # frank-ocean is seeded; first call increments to 1
    r1 = client.get("/descriptors/frank-ocean")
    assert r1.status_code == 200
    body = r1.json()
    assert body["canonical_name"] == "Frank Ocean"
    assert body["use_count"] == 1
    r2 = client.get("/descriptors/frank-ocean")
    assert r2.json()["use_count"] == 2


def test_get_descriptor_normalizes_name(client):
    # "The Frank Ocean" should normalize to "frank ocean" → hit
    resp = client.get("/descriptors/the%20frank%20ocean")
    assert resp.status_code == 200
    assert resp.json()["canonical_name"] == "Frank Ocean"


def test_get_descriptor_miss_invokes_llm_and_caches(client):
    fake_payload = {
        "descriptor_short": "Bright tenor lead with reverb-soaked production.",
        "descriptor_long": "A bright tenor lead. Production is reverb-drenched with bouncy synth bass and bright pop snares; vocals double-tracked on chorus.",
        "vocal_attributes": {"range": "tenor", "character": "bright"},
        "production_attrs": {"tempo_zone": "100-120"},
        "genre_context": "alt-pop",
    }
    with patch("songwriter.api.routes.descriptors.ask_claude_json", return_value=fake_payload) as m:
        resp = client.get("/descriptors/some-new-artist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "auto-llm"
    assert body["quality_state"] == "unverified"
    assert body["use_count"] == 1
    # second request hits cache, no new LLM call
    with patch("songwriter.api.routes.descriptors.ask_claude_json") as m2:
        client.get("/descriptors/some-new-artist")
        m2.assert_not_called()


def test_descriptor_scrubs_burn_list_words(client):
    fake = {
        "descriptor_short": "A neon, ghost-like presence with chrome production.",
        "descriptor_long": "Long form. Neon glow in the chorus, ghost-like delays, chrome high-end. " * 3,
        "vocal_attributes": {},
        "production_attrs": {},
        "genre_context": "synth-pop",
    }
    with patch("songwriter.api.routes.descriptors.ask_claude_json", return_value=fake):
        resp = client.get("/descriptors/another-new-artist")
    body = resp.json()
    # burn-list words must be scrubbed from short and long
    for w in ("neon", "ghost", "chrome"):
        assert w.lower() not in body["descriptor_short"].lower()
        assert w.lower() not in body["descriptor_long"].lower()
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

File: `src/songwriter/api/routes/descriptors.py`

```python
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from songwriter.api.deps import get_db
from songwriter.api.llm import ask_claude_json


router = APIRouter()


_HONORIFICS = re.compile(r"\b(mr|mrs|ms|the|dj)\b\.?", re.IGNORECASE)


def _normalize(name: str) -> str:
    s = _HONORIFICS.sub("", name).strip().lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _scrub(text: str, burn_words: list[str]) -> str:
    out = text
    for w in burn_words:
        out = re.sub(rf"\b{re.escape(w)}\b", "[scrubbed]", out, flags=re.IGNORECASE)
    return out


_GEN_PROMPT_TEMPLATE = """\
Describe the artist '{name}' for use in a music-generation prompt. Output STRICT JSON only.
Required keys: descriptor_short (≤30 words), descriptor_long (~80-120 words),
vocal_attributes (object), production_attrs (object), genre_context (string).
Constraints:
- The artist's name must NOT appear inside descriptor_short or descriptor_long.
- Describe vocal timbre, register, attack profile.
- Describe production: instrumentation, mix character, tempo zone.
- Avoid overused AI words like neon, chrome, ghost, midnight, shadow, silver.
- No song titles, no copyrighted lyric content.
Output the JSON inside a ```json fenced block.
"""


def _hydrate(row: sqlite3.Row) -> dict:
    d = dict(row)
    for c in ("vocal_attributes", "production_attrs"):
        d[c] = json.loads(d[c]) if d.get(c) else None
    return d


@router.get("/descriptors/{name}")
def get_descriptor(name: str, db: Annotated[sqlite3.Connection, Depends(get_db)]):
    normalized = _normalize(name)
    if not normalized:
        raise HTTPException(400, "empty name")

    row = db.execute(
        "SELECT * FROM artist_descriptor_cache WHERE normalized_name = ?", (normalized,)
    ).fetchone()
    if row is not None:
        db.execute(
            """
            UPDATE artist_descriptor_cache
            SET use_count = use_count + 1, last_used_at = ?
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), row["id"]),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM artist_descriptor_cache WHERE id = ?", (row["id"],)
        ).fetchone()
        return _hydrate(row)

    # MISS — generate via LLM
    payload = ask_claude_json(_GEN_PROMPT_TEMPLATE.format(name=name))
    if not isinstance(payload, dict) or "descriptor_short" not in payload:
        raise HTTPException(502, "LLM returned malformed descriptor")

    burn_rows = db.execute("SELECT word FROM suno_burn_list").fetchall()
    burn_words = [r["word"] for r in burn_rows]
    descriptor_short = _scrub(payload["descriptor_short"], burn_words)
    descriptor_long = _scrub(payload["descriptor_long"], burn_words)

    db.execute(
        """
        INSERT INTO artist_descriptor_cache
          (normalized_name, canonical_name, descriptor, descriptor_short, descriptor_long,
           vocal_attributes, production_attrs, genre_context,
           source, quality_state, use_count, last_used_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,1,?)
        """,
        (
            normalized, name, descriptor_short, descriptor_short, descriptor_long,
            json.dumps(payload.get("vocal_attributes") or {}),
            json.dumps(payload.get("production_attrs") or {}),
            payload.get("genre_context"),
            "auto-llm", "unverified",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()
    row = db.execute(
        "SELECT * FROM artist_descriptor_cache WHERE normalized_name = ?", (normalized,)
    ).fetchone()
    return _hydrate(row)
```

- [ ] **Step 4: Register router. Run, verify PASS. Commit**

```bash
git add src/songwriter/api/main.py src/songwriter/api/routes/descriptors.py tests/api/test_descriptors.py
git commit -m "feat(api): add descriptor cache with auto-LLM on miss + burn-list scrub"
```

---

## Task 8: Song JSON schemas (pydantic models)

**Files:**
- Create: `src/songwriter/api/schemas.py`
- Create: `tests/api/test_schemas.py`

Pydantic v2 models. These are the cross-plan contract — the skill plan and the UI plan both consume this shape.

- [ ] **Step 1: Write failing test**

File: `tests/api/test_schemas.py`

```python
import pytest
from pydantic import ValidationError

from songwriter.api.schemas import (
    Song, Section, SectionValidation, Intent, Production, IntentStory,
    Request as SongRequest, SunoPrompt,
)


def test_minimal_song_validates():
    s = Song(
        id="2026-04-30-test",
        title="Test",
        genre="pop",
        sub_genre="dance-pop",
        intent=Intent(topic="test", emotion_arc="defiance",
                      story=IntentStory(event="x", emotion="y", resolution="z")),
        production=Production(bpm=120, structure_template="pop.standard", energy_curve=[0.5]),
        sections=[],
    )
    assert s.id == "2026-04-30-test"


def test_section_with_validation_results():
    sec = Section(
        id="v1",
        label="Verse 1",
        lock_state="draft",
        lyrics=["a", "b"],
        cadence_pattern="melodic-glide",
        validation=SectionValidation(
            singability="pass",
            cadence="warn",
            phonetic_texture="pass",
            rhyme_cadence="pass",
            story_sentence="unrun",
            warnings=["second line fails singability cadence alignment"],
        ),
    )
    assert sec.validation.cadence == "warn"


def test_invalid_lock_state_raises():
    with pytest.raises(ValidationError):
        Section(id="v1", label="Verse 1", lock_state="superlocked",
                lyrics=[], cadence_pattern="pop-hook")


def test_song_round_trips_through_json(tmp_path):
    s = Song(
        id="x", title="X", genre="pop", sub_genre="alt-pop",
        intent=Intent(topic="t", emotion_arc="surrender",
                      story=IntentStory(event="e", emotion="m", resolution="r")),
        production=Production(bpm=88, structure_template="pop.standard", energy_curve=[0.4]),
        sections=[Section(id="v1", label="Verse 1", lock_state="draft",
                          lyrics=["one"], cadence_pattern="melodic-glide")],
    )
    p = tmp_path / "x.json"
    p.write_text(s.model_dump_json(indent=2))
    s2 = Song.model_validate_json(p.read_text())
    assert s2 == s


def test_request_entry_shape():
    r = SongRequest(type="suggest_alternatives", section="v1", line=2, count=3, constraint="more vulnerable")
    assert r.line == 2
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement `schemas.py`**

```python
"""Pydantic v2 models. Cross-plan contract — shared with the Claude Code skill and the UI."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


LockState = Literal["draft", "edited", "locked"]
RuleResult = Literal["pass", "warn", "fail", "unrun"]


class IntentStory(BaseModel):
    event: str
    emotion: str
    resolution: str


class Intent(BaseModel):
    topic: str
    emotion_arc: str
    story: IntentStory


class Production(BaseModel):
    bpm: int = Field(..., ge=30, le=240)
    structure_template: str
    energy_curve: list[float] = Field(default_factory=list)


class SectionValidation(BaseModel):
    singability: RuleResult = "unrun"
    cadence: RuleResult = "unrun"
    phonetic_texture: RuleResult = "unrun"
    rhyme_cadence: RuleResult = "unrun"
    story_sentence: RuleResult = "unrun"
    warnings: list[str] = Field(default_factory=list)


class Section(BaseModel):
    id: str
    label: str
    lock_state: LockState
    lyrics: list[str] = Field(default_factory=list)
    cadence_pattern: str
    validation: SectionValidation = Field(default_factory=SectionValidation)
    phonetic_overlay: list[dict] = Field(default_factory=list)


class SunoPrompt(BaseModel):
    current: str = ""
    history: list[dict] = Field(default_factory=list)


class Request(BaseModel):
    type: Literal["suggest_alternatives", "tighten_cadence", "rewrite_section", "regen_descriptor"]
    section: str | None = None
    line: int | None = None
    count: int | None = None
    constraint: str | None = None
    payload: dict | None = None


class Song(BaseModel):
    id: str
    title: str
    created: datetime = Field(default_factory=datetime.utcnow)
    modified: datetime = Field(default_factory=datetime.utcnow)
    genre: str
    sub_genre: str
    songwriter_lens: str | None = None
    intent: Intent
    production: Production
    sections: list[Section] = Field(default_factory=list)
    suno_prompt: SunoPrompt = Field(default_factory=SunoPrompt)
    requests: list[Request] = Field(default_factory=list)
    notes: str = ""
    last_modified_by: Literal["ui", "skill", "api"] = "api"
```

- [ ] **Step 4: Run, verify PASS. Commit**

```bash
git add src/songwriter/api/schemas.py tests/api/test_schemas.py
git commit -m "feat(api): add Pydantic song-state schemas (cross-plan contract)"
```

---

## Task 9: Song-file IO + CRUD endpoints

**Files:**
- Create: `src/songwriter/api/songs_io.py`
- Create: `src/songwriter/api/routes/songs.py`
- Modify: `src/songwriter/api/main.py`
- Create: `tests/api/test_songs_io.py`
- Create: `tests/api/test_songs_crud.py`

`songs_io.py` is the disk layer (slug → path, read, write atomically, list); `routes/songs.py` is the HTTP layer.

- [ ] **Step 1: Write failing test for `songs_io.py`**

File: `tests/api/test_songs_io.py`

```python
import json
from pathlib import Path

import pytest

from songwriter.api.songs_io import path_for_slug, read_song, write_song, list_song_slugs
from songwriter.api.schemas import Song, Intent, IntentStory, Production


def _sample_song(slug="x") -> Song:
    return Song(
        id=slug, title="Sample", genre="pop", sub_genre="alt-pop",
        intent=Intent(topic="t", emotion_arc="surrender",
                      story=IntentStory(event="e", emotion="m", resolution="r")),
        production=Production(bpm=88, structure_template="pop.standard", energy_curve=[0.4]),
    )


def test_path_for_slug(tmp_path):
    p = path_for_slug(tmp_path, "abc")
    assert p == tmp_path / "abc.json"


def test_write_and_read_round_trip(tmp_path):
    s = _sample_song("trip")
    write_song(tmp_path, s)
    s2 = read_song(tmp_path, "trip")
    assert s2.title == "Sample"


def test_write_is_atomic(tmp_path):
    s = _sample_song("atomic")
    write_song(tmp_path, s)
    # crash sim: temp file should be gone after successful write
    assert not list(tmp_path.glob("*.tmp"))


def test_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_song(tmp_path, "ghost")


def test_list_song_slugs(tmp_path):
    write_song(tmp_path, _sample_song("a"))
    write_song(tmp_path, _sample_song("b"))
    (tmp_path / "ignore.txt").write_text("nope")
    assert sorted(list_song_slugs(tmp_path)) == ["a", "b"]
```

- [ ] **Step 2: Implement `songs_io.py`**

```python
import os
from pathlib import Path

from songwriter.api.schemas import Song


def path_for_slug(songs_dir: Path, slug: str) -> Path:
    return songs_dir / f"{slug}.json"


def read_song(songs_dir: Path, slug: str) -> Song:
    p = path_for_slug(songs_dir, slug)
    if not p.exists():
        raise FileNotFoundError(slug)
    return Song.model_validate_json(p.read_text())


def write_song(songs_dir: Path, song: Song) -> Path:
    songs_dir.mkdir(parents=True, exist_ok=True)
    target = path_for_slug(songs_dir, song.id)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(song.model_dump_json(indent=2))
    os.replace(tmp, target)
    return target


def list_song_slugs(songs_dir: Path) -> list[str]:
    if not songs_dir.exists():
        return []
    return sorted(p.stem for p in songs_dir.glob("*.json"))
```

- [ ] **Step 3: Write failing test for `routes/songs.py`**

File: `tests/api/test_songs_crud.py`

```python
def _new_song_payload(slug="alpha"):
    return {
        "id": slug, "title": "Alpha",
        "genre": "pop", "sub_genre": "alt-pop",
        "intent": {
            "topic": "first song", "emotion_arc": "surrender",
            "story": {"event": "e", "emotion": "m", "resolution": "r"},
        },
        "production": {"bpm": 88, "structure_template": "pop.standard", "energy_curve": [0.4]},
        "sections": [],
    }


def test_create_song_persists_to_disk(client, settings):
    resp = client.post("/songs", json=_new_song_payload("alpha"))
    assert resp.status_code == 201
    assert (settings.songs_dir / "alpha.json").exists()


def test_create_duplicate_slug_409(client):
    client.post("/songs", json=_new_song_payload("dup"))
    resp = client.post("/songs", json=_new_song_payload("dup"))
    assert resp.status_code == 409


def test_get_song(client):
    client.post("/songs", json=_new_song_payload("getme"))
    resp = client.get("/songs/getme")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Alpha"


def test_get_missing_404(client):
    assert client.get("/songs/ghost").status_code == 404


def test_list_songs(client):
    client.post("/songs", json=_new_song_payload("one"))
    client.post("/songs", json=_new_song_payload("two"))
    resp = client.get("/songs")
    assert resp.status_code == 200
    slugs = {s["id"] for s in resp.json()}
    assert {"one", "two"} <= slugs


def test_put_song_updates(client):
    client.post("/songs", json=_new_song_payload("putme"))
    payload = _new_song_payload("putme")
    payload["title"] = "Renamed"
    resp = client.put("/songs/putme", json=payload)
    assert resp.status_code == 200
    assert client.get("/songs/putme").json()["title"] == "Renamed"


def test_put_slug_mismatch_400(client):
    client.post("/songs", json=_new_song_payload("p1"))
    payload = _new_song_payload("p1")
    payload["id"] = "different"
    resp = client.put("/songs/p1", json=payload)
    assert resp.status_code == 400
```

- [ ] **Step 4: Implement `routes/songs.py`**

```python
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from songwriter.api.deps import get_settings
from songwriter.api.schemas import Song
from songwriter.api.settings import Settings
from songwriter.api.songs_io import list_song_slugs, path_for_slug, read_song, write_song


router = APIRouter()


@router.get("/songs")
def list_songs(settings: Annotated[Settings, Depends(get_settings)]) -> list[dict]:
    out = []
    for slug in list_song_slugs(settings.songs_dir):
        try:
            song = read_song(settings.songs_dir, slug)
        except Exception:
            continue
        out.append({
            "id": song.id, "title": song.title, "genre": song.genre,
            "sub_genre": song.sub_genre, "songwriter_lens": song.songwriter_lens,
            "modified": song.modified.isoformat(),
        })
    return out


@router.post("/songs", status_code=201)
def create_song(song: Song, settings: Annotated[Settings, Depends(get_settings)]) -> Song:
    if path_for_slug(settings.songs_dir, song.id).exists():
        raise HTTPException(409, f"song {song.id!r} already exists")
    song.last_modified_by = "api"
    song.modified = datetime.now(timezone.utc)
    write_song(settings.songs_dir, song)
    return song


@router.get("/songs/{slug}")
def get_song(slug: str, settings: Annotated[Settings, Depends(get_settings)]) -> Song:
    try:
        return read_song(settings.songs_dir, slug)
    except FileNotFoundError:
        raise HTTPException(404, f"song {slug!r} not found")


@router.put("/songs/{slug}")
def update_song(
    slug: str,
    song: Song,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Song:
    if song.id != slug:
        raise HTTPException(400, "song.id does not match URL slug")
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song.last_modified_by = "api"
    song.modified = datetime.now(timezone.utc)
    write_song(settings.songs_dir, song)
    return song
```

- [ ] **Step 5: Register router. Run all tests, verify PASS. Commit**

```bash
git add src/songwriter/api/main.py src/songwriter/api/songs_io.py src/songwriter/api/routes/songs.py tests/api/test_songs_io.py tests/api/test_songs_crud.py
git commit -m "feat(api): song JSON IO + CRUD endpoints"
```

---

## Task 10: Validation tokenizer + DB phonetic resolver

**Files:**
- Create: `src/songwriter/api/validation/__init__.py`
- Create: `src/songwriter/api/validation/tokenizer.py`
- Create: `tests/validation/__init__.py`
- Create: `tests/validation/conftest.py`
- Create: `tests/validation/test_tokenizer.py`

The tokenizer takes a lyric line, splits into words, looks each up in the `words` table, and returns a list of `WordToken` objects with phonetic data attached. Words missing from the DB are returned with `unknown=True` and skipped by validators.

- [ ] **Step 1: Test infrastructure**

File: `tests/validation/conftest.py`

```python
from pathlib import Path
import pytest

from songwriter.seeds import db as db_module
from songwriter.seeds.build import run as build_run


@pytest.fixture(scope="session")
def built_db(tmp_path_factory):
    target = tmp_path_factory.mktemp("data") / "songwriter.db"
    cache_dir = tmp_path_factory.mktemp("cache")
    fixture = Path(__file__).parent.parent / "fixtures" / "cmudict_vocab_words.txt"
    (cache_dir / "cmudict.dict").write_text(fixture.read_text())
    build_run(db_path=target, cache_dir=cache_dir)
    return target


@pytest.fixture
def conn(built_db):
    c = db_module.connect(built_db)
    yield c
    c.close()
```

- [ ] **Step 2: Failing test**

File: `tests/validation/test_tokenizer.py`

```python
from songwriter.api.validation.tokenizer import tokenize_line


def test_tokenize_drops_punctuation_and_lowercases(conn):
    toks = tokenize_line("You called me late!", conn)
    assert [t.word for t in toks] == ["you", "called", "me", "late"]


def test_tokenize_attaches_phonetic_data(conn):
    toks = tokenize_line("love above", conn)
    assert toks[0].word == "love"
    assert toks[0].rhyme_class == "AH-V"
    assert toks[1].rhyme_class == "AH-V"
    assert toks[0].syllables == 1


def test_tokenize_marks_unknown_words(conn):
    toks = tokenize_line("schmlorp love", conn)
    assert toks[0].unknown is True
    assert toks[0].syllables == 0
    assert toks[1].unknown is False


def test_tokenize_empty_line(conn):
    assert tokenize_line("", conn) == []
```

- [ ] **Step 3: Implement**

File: `src/songwriter/api/validation/tokenizer.py`

```python
import re
import sqlite3
from dataclasses import dataclass


@dataclass
class WordToken:
    word: str
    unknown: bool
    syllables: int
    stress_pattern: str
    rhyme_class: str
    vowel_shape: str
    first_syllable_attack: str
    consonant_density: float
    ipa: str


_WORD_RE = re.compile(r"[a-z']+", re.IGNORECASE)


def tokenize_line(line: str, conn: sqlite3.Connection) -> list[WordToken]:
    raw_words = [m.group(0).lower().strip("'") for m in _WORD_RE.finditer(line)]
    raw_words = [w for w in raw_words if w]
    if not raw_words:
        return []
    placeholders = ",".join("?" * len(raw_words))
    rows = conn.execute(
        f"""
        SELECT word, syllables, stress_pattern, rhyme_class, vowel_shape,
               first_syllable_attack, consonant_density, ipa
        FROM words WHERE word IN ({placeholders}) AND language = 'en'
        """,
        raw_words,
    ).fetchall()
    by_word = {r["word"]: r for r in rows}
    out: list[WordToken] = []
    for w in raw_words:
        r = by_word.get(w)
        if r is None:
            out.append(WordToken(
                word=w, unknown=True, syllables=0, stress_pattern="",
                rhyme_class="", vowel_shape="", first_syllable_attack="",
                consonant_density=0.0, ipa="",
            ))
        else:
            out.append(WordToken(
                word=w, unknown=False,
                syllables=r["syllables"] or 0,
                stress_pattern=r["stress_pattern"] or "",
                rhyme_class=r["rhyme_class"] or "",
                vowel_shape=r["vowel_shape"] or "",
                first_syllable_attack=r["first_syllable_attack"] or "",
                consonant_density=r["consonant_density"] or 0.0,
                ipa=r["ipa"] or "",
            ))
    return out
```

- [ ] **Step 4: Run, verify PASS. Commit**

```bash
git add src/songwriter/api/validation tests/validation
git commit -m "feat(validation): line tokenizer with DB phonetic resolver"
```

---

## Task 11: Deterministic validation engines (Singability + Cadence + Rhyme-Cadence + Phonetic Texture)

**Files:**
- Create: `src/songwriter/api/validation/singability.py`
- Create: `src/songwriter/api/validation/cadence.py`
- Create: `src/songwriter/api/validation/rhyme_cadence.py`
- Create: `src/songwriter/api/validation/phonetic_texture.py`
- Create: `tests/validation/test_singability.py`
- Create: `tests/validation/test_cadence.py`
- Create: `tests/validation/test_rhyme_cadence.py`
- Create: `tests/validation/test_phonetic_texture.py`

Each engine has a single function `check(section, ctx) -> RuleOutcome` where `RuleOutcome` is `("pass" | "warn" | "fail", list[str])` (verdict + warning messages). `ctx` is a small dataclass that bundles the cadence pattern row, the section's emotion, the production fingerprint negative-descriptors list, and a DB connection.

- [ ] **Step 1: Common types**

Append to: `src/songwriter/api/validation/__init__.py`

```python
from dataclasses import dataclass
from typing import Literal

Verdict = Literal["pass", "warn", "fail"]


@dataclass
class RuleOutcome:
    verdict: Verdict
    warnings: list[str]


@dataclass
class CadencePattern:
    slug: str
    syllable_template: str
    stress_template: str
    rhyme_compatibility: dict


@dataclass
class ValidationContext:
    cadence_pattern: CadencePattern | None
    emotion: str
    sub_genre: str
```

- [ ] **Step 2: Singability**

File: `src/songwriter/api/validation/singability.py`

Singability fails if a line's total syllable count is too far from the cadence pattern's `syllable_template` (a single number like `"8"`, a range like `"6-9"`, or `"?"` for wildcard). Tolerance: ±2 syllables for fixed counts, exact for ranges, no-op for wildcards.

```python
import re

from songwriter.api.validation import RuleOutcome, ValidationContext
from songwriter.api.validation.tokenizer import WordToken


def _syllables_in_line(tokens: list[WordToken]) -> int:
    return sum(t.syllables for t in tokens if not t.unknown)


def _parse_template(s: str) -> tuple[int | None, int | None]:
    s = s.strip()
    if s == "?" or not s:
        return None, None
    m = re.match(r"^(\d+)-(\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    if s.isdigit():
        n = int(s)
        return n - 2, n + 2  # ±2 tolerance
    return None, None


def check_line(tokens: list[WordToken], ctx: ValidationContext) -> RuleOutcome:
    if ctx.cadence_pattern is None:
        return RuleOutcome("warn", ["no cadence pattern set; cannot check singability"])
    lo, hi = _parse_template(ctx.cadence_pattern.syllable_template)
    if lo is None:
        return RuleOutcome("pass", [])
    n = _syllables_in_line(tokens)
    if n < lo:
        return RuleOutcome("fail", [f"line has {n} syllables; cadence expects {lo}-{hi}"])
    if n > hi:
        return RuleOutcome("warn", [f"line has {n} syllables; cadence expects {lo}-{hi}"])
    return RuleOutcome("pass", [])
```

Test (`tests/validation/test_singability.py`):

```python
from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.singability import check_line
from songwriter.api.validation.tokenizer import tokenize_line


def _ctx(template: str):
    return ValidationContext(
        cadence_pattern=CadencePattern(
            slug="x", syllable_template=template, stress_template="?", rhyme_compatibility={}
        ),
        emotion="surrender", sub_genre="pop.alt-pop",
    )


def test_singability_pass_in_range(conn):
    toks = tokenize_line("you called me late tonight", conn)
    res = check_line(toks, _ctx("6-9"))
    assert res.verdict == "pass"


def test_singability_fail_below_range(conn):
    toks = tokenize_line("late", conn)
    res = check_line(toks, _ctx("6-9"))
    assert res.verdict == "fail"


def test_singability_warn_above_range(conn):
    toks = tokenize_line("she called me very very late tonight after work", conn)
    res = check_line(toks, _ctx("6-9"))
    assert res.verdict == "warn"


def test_singability_wildcard_passes(conn):
    toks = tokenize_line("anything goes here", conn)
    res = check_line(toks, _ctx("?"))
    assert res.verdict == "pass"
```

- [ ] **Step 3: Cadence**

File: `src/songwriter/api/validation/cadence.py`

Cadence fails if the concatenated stress pattern of the line's words doesn't align with the cadence's `stress_template`. We compare prefix-aligned (first N stressed positions); allow `?` wildcards.

```python
from songwriter.api.validation import RuleOutcome, ValidationContext
from songwriter.api.validation.tokenizer import WordToken


def _line_stress(tokens: list[WordToken]) -> str:
    return "".join(t.stress_pattern for t in tokens if not t.unknown)


def check_line(tokens: list[WordToken], ctx: ValidationContext) -> RuleOutcome:
    if ctx.cadence_pattern is None:
        return RuleOutcome("warn", ["no cadence pattern set"])
    template = ctx.cadence_pattern.stress_template
    if not template or template == "?":
        return RuleOutcome("pass", [])
    actual = _line_stress(tokens)
    cmp_len = min(len(template), len(actual))
    mismatches = []
    for i in range(cmp_len):
        if template[i] == "?":
            continue
        if template[i] != actual[i]:
            mismatches.append(i)
    if not mismatches:
        return RuleOutcome("pass", [])
    if len(mismatches) <= 1:
        return RuleOutcome("warn", [f"cadence drift at position {mismatches[0]}"])
    return RuleOutcome("fail", [
        f"cadence drift: line stress {actual!r} vs template {template!r} differs at {mismatches}"
    ])
```

Test:

```python
from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.cadence import check_line
from songwriter.api.validation.tokenizer import tokenize_line


def _ctx(stress: str):
    return ValidationContext(
        cadence_pattern=CadencePattern(
            slug="x", syllable_template="?", stress_template=stress, rhyme_compatibility={}
        ),
        emotion="x", sub_genre="x",
    )


def test_cadence_wildcard_passes(conn):
    toks = tokenize_line("you called me late tonight", conn)
    assert check_line(toks, _ctx("?")).verdict == "pass"


def test_cadence_pass_when_stress_matches(conn):
    # "love" has stress pattern "1"; template "1" passes
    toks = tokenize_line("love", conn)
    assert check_line(toks, _ctx("1")).verdict == "pass"


def test_cadence_drift_warns(conn):
    # "love love" → "11"; template "10" → 1 mismatch → warn
    toks = tokenize_line("love love", conn)
    assert check_line(toks, _ctx("10")).verdict == "warn"
```

- [ ] **Step 4: Rhyme-Cadence Interaction**

File: `src/songwriter/api/validation/rhyme_cadence.py`

This rule checks the *section's* line endings: do they form a valid rhyme scheme for this cadence's `rhyme_compatibility.end` list? Returns `pass` if at least 2 of the last words share a rhyme class **AND** that rhyme style (perfect/near/slant) is in the compatibility list. `warn` if the line endings don't rhyme at all in a section that requires it.

```python
from collections import Counter

from songwriter.api.validation import RuleOutcome, ValidationContext
from songwriter.api.validation.tokenizer import WordToken


def check_section(line_tokens: list[list[WordToken]], ctx: ValidationContext) -> RuleOutcome:
    if ctx.cadence_pattern is None:
        return RuleOutcome("warn", ["no cadence pattern"])
    end_classes: list[str] = []
    for line in line_tokens:
        last = next((t for t in reversed(line) if not t.unknown and t.rhyme_class), None)
        if last:
            end_classes.append(last.rhyme_class)
    if len(end_classes) < 2:
        return RuleOutcome("warn", ["section has fewer than 2 line endings with phonetic data"])
    common = Counter(end_classes).most_common(1)[0]
    if common[1] >= 2:
        # at least one rhyme pair → check perfect-rhyme allowed
        if "perfect" in (ctx.cadence_pattern.rhyme_compatibility.get("end") or []):
            return RuleOutcome("pass", [])
        return RuleOutcome("warn", [f"rhyme pair on '{common[0]}' but cadence allows {ctx.cadence_pattern.rhyme_compatibility}"])
    return RuleOutcome("warn", ["no rhyme pair detected across line endings"])
```

Test:

```python
from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.rhyme_cadence import check_section
from songwriter.api.validation.tokenizer import tokenize_line


def _ctx(rhyme_compat):
    return ValidationContext(
        cadence_pattern=CadencePattern(
            slug="x", syllable_template="?", stress_template="?", rhyme_compatibility=rhyme_compat
        ),
        emotion="x", sub_genre="x",
    )


def test_rhyme_pair_passes_when_perfect_allowed(conn):
    lines = [tokenize_line("you called me late we", conn),  # ends in "we"
             tokenize_line("she said the same to me", conn)]  # ends in "me" — both rhyme in IY
    assert check_section(lines, _ctx({"end": ["perfect", "near"]})).verdict == "pass"


def test_no_rhyme_warns(conn):
    lines = [tokenize_line("love", conn), tokenize_line("late", conn)]
    assert check_section(lines, _ctx({"end": ["perfect"]})).verdict == "warn"
```

- [ ] **Step 5: Phonetic Texture**

File: `src/songwriter/api/validation/phonetic_texture.py`

Phonetic Texture checks whether the line's average `consonant_density` and dominant `first_syllable_attack` align with what the section's `emotion` calls for. Heuristics:

- `surrender` / `nostalgia` / `intimacy` emotions want **low** consonant density (≤0.35) and **soft / vowel** attacks.
- `defiance` / `escalation` want **high** density (≥0.45) and **hard** attacks.
- `collapse` is the same as surrender.
- `redemption` is balanced (no constraint).

```python
from collections import Counter
from statistics import mean

from songwriter.api.validation import RuleOutcome, ValidationContext
from songwriter.api.validation.tokenizer import WordToken


_SOFT_EMOTIONS = {"surrender", "nostalgia", "intimacy", "collapse"}
_HARD_EMOTIONS = {"defiance", "escalation"}


def check_line(tokens: list[WordToken], ctx: ValidationContext) -> RuleOutcome:
    known = [t for t in tokens if not t.unknown]
    if not known:
        return RuleOutcome("warn", ["no recognized words on line"])
    avg_density = mean(t.consonant_density for t in known)
    attacks = Counter(t.first_syllable_attack for t in known)
    dominant_attack = attacks.most_common(1)[0][0]

    if ctx.emotion in _SOFT_EMOTIONS:
        if avg_density > 0.45:
            return RuleOutcome("warn", [
                f"consonant density {avg_density:.2f} too hard for emotion {ctx.emotion!r}"
            ])
        if dominant_attack == "hard":
            return RuleOutcome("warn", [f"hard attack mismatches soft emotion {ctx.emotion!r}"])
        return RuleOutcome("pass", [])
    if ctx.emotion in _HARD_EMOTIONS:
        if avg_density < 0.30:
            return RuleOutcome("warn", [
                f"consonant density {avg_density:.2f} too soft for emotion {ctx.emotion!r}"
            ])
        return RuleOutcome("pass", [])
    return RuleOutcome("pass", [])
```

Test:

```python
from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.phonetic_texture import check_line
from songwriter.api.validation.tokenizer import tokenize_line


def _ctx(emotion: str):
    return ValidationContext(
        cadence_pattern=None, emotion=emotion, sub_genre="x",
    )


def test_soft_emotion_pass_with_soft_words(conn):
    toks = tokenize_line("love linen pillow leaned", conn)  # mostly soft attacks, low density
    assert check_line(toks, _ctx("surrender")).verdict == "pass"


def test_soft_emotion_warn_with_hard_attacks(conn):
    toks = tokenize_line("typed kept paid stayed", conn)  # T/K/P/S — many hard attacks
    res = check_line(toks, _ctx("intimacy"))
    assert res.verdict == "warn"
```

- [ ] **Step 6: Run all 4 test files, verify PASS. Commit**

```bash
git add src/songwriter/api/validation tests/validation
git commit -m "feat(validation): deterministic engines (singability, cadence, rhyme-cadence, phonetic-texture)"
```

---

## Task 12: LLM-judged engine — Story / Sentence semantic checks

**Files:**
- Create: `src/songwriter/api/validation/story_sentence.py`
- Create: `tests/validation/test_story_sentence.py`

This engine batches Story Rule + Sentence Rule (semantic logic, continuity, narrative consistency) into one LLM call per section. The prompt asks Claude to return strict JSON with per-line verdicts.

- [ ] **Step 1: Test (mocking the LLM call)**

```python
from unittest.mock import patch

from songwriter.api.validation.story_sentence import check_section
from songwriter.api.validation import ValidationContext


def _ctx():
    return ValidationContext(cadence_pattern=None, emotion="surrender", sub_genre="pop.alt-pop")


def test_story_sentence_pass(monkeypatch):
    fake = {"verdict": "pass", "per_line": [{"line_index": 0, "verdict": "pass", "note": "ok"}]}
    with patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake):
        outcome = check_section(["a single line"], _ctx(), intent_story={"event":"e","emotion":"m","resolution":"r"})
    assert outcome.verdict == "pass"


def test_story_sentence_fail_aggregates_warnings():
    fake = {
        "verdict": "fail",
        "per_line": [
            {"line_index": 0, "verdict": "pass", "note": "ok"},
            {"line_index": 1, "verdict": "fail", "note": "breaks narrative continuity"},
        ],
    }
    with patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake):
        outcome = check_section(["a", "b"], _ctx(), intent_story={"event":"e","emotion":"m","resolution":"r"})
    assert outcome.verdict == "fail"
    assert any("continuity" in w for w in outcome.warnings)


def test_story_sentence_handles_llm_error(monkeypatch):
    from songwriter.api.llm import LLMError
    with patch("songwriter.api.validation.story_sentence.ask_claude_json", side_effect=LLMError("boom")):
        outcome = check_section(["a"], _ctx(), intent_story={"event":"e","emotion":"m","resolution":"r"})
    assert outcome.verdict == "warn"
    assert any("LLM" in w or "boom" in w for w in outcome.warnings)
```

- [ ] **Step 2: Implement**

File: `src/songwriter/api/validation/story_sentence.py`

```python
from songwriter.api.llm import LLMError, ask_claude_json
from songwriter.api.validation import RuleOutcome, ValidationContext


_PROMPT = """\
You are validating a song section for narrative coherence and sentence-level logic.

Section emotion: {emotion}
Story spec: event={event!r}, emotion={emotion_arc!r}, resolution={resolution!r}
Lines:
{lines}

For each line, judge:
- Sentence Logic: does the line make grammatical and semantic sense?
- Context Continuity: does the line follow naturally from the previous line?
- Narrative Consistency: does the line fit the story spec above?

Output STRICT JSON inside a ```json block. Schema:
{{"verdict": "pass" | "warn" | "fail",
  "per_line": [
    {{"line_index": <int>, "verdict": "pass" | "warn" | "fail", "note": "<short reason>"}}
  ]
}}
The overall verdict is the worst per-line verdict.
"""


def check_section(lyrics: list[str], ctx: ValidationContext, *, intent_story: dict) -> RuleOutcome:
    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lyrics))
    prompt = _PROMPT.format(
        emotion=ctx.emotion,
        event=intent_story.get("event", ""),
        emotion_arc=intent_story.get("emotion", ""),
        resolution=intent_story.get("resolution", ""),
        lines=numbered or "(empty section)",
    )
    try:
        payload = ask_claude_json(prompt)
    except LLMError as e:
        return RuleOutcome("warn", [f"LLM-judged check failed: {e}"])
    if not isinstance(payload, dict):
        return RuleOutcome("warn", ["LLM-judged check: malformed response"])
    verdict = payload.get("verdict", "warn")
    if verdict not in ("pass", "warn", "fail"):
        verdict = "warn"
    warnings: list[str] = []
    for entry in payload.get("per_line") or []:
        if entry.get("verdict") in ("warn", "fail") and entry.get("note"):
            warnings.append(f"line {entry.get('line_index')}: {entry['note']}")
    return RuleOutcome(verdict, warnings)
```

- [ ] **Step 3: Run, verify PASS. Commit**

```bash
git add src/songwriter/api/validation/story_sentence.py tests/validation/test_story_sentence.py
git commit -m "feat(validation): LLM-judged story+sentence engine via claude --print"
```

---

## Task 13: Validation orchestrator + endpoint

**Files:**
- Create: `src/songwriter/api/validation/orchestrator.py`
- Create: `src/songwriter/api/routes/validate.py`
- Modify: `src/songwriter/api/main.py`
- Create: `tests/api/test_validate.py`

The orchestrator accepts a `Song`, looks up each section's cadence pattern from the DB, runs all engines, writes the results back into `section.validation`, and returns the updated Song. The endpoint is `POST /songs/{slug}/validate?include_llm=<bool>` (default true).

- [ ] **Step 1: Failing test**

```python
from unittest.mock import patch


def _payload(slug="vsong", section_lyrics=None):
    return {
        "id": slug, "title": "V",
        "genre": "rnb", "sub_genre": "alt-rnb",
        "intent": {
            "topic": "test", "emotion_arc": "surrender",
            "story": {"event": "e", "emotion": "m", "resolution": "r"},
        },
        "production": {"bpm": 72, "structure_template": "rnb.intimate-confession", "energy_curve": [0.4]},
        "sections": [{
            "id": "v1", "label": "Verse 1", "lock_state": "draft",
            "cadence_pattern": "melodic-glide",
            "lyrics": section_lyrics or ["you called me late", "said you couldn't sleep"],
        }],
    }


def test_validate_runs_deterministic_only_when_skip_llm(client):
    client.post("/songs", json=_payload("v1"))
    resp = client.post("/songs/v1/validate?include_llm=false")
    assert resp.status_code == 200
    sec = resp.json()["sections"][0]["validation"]
    # deterministic engines ran
    assert sec["singability"] in ("pass", "warn", "fail")
    assert sec["cadence"] in ("pass", "warn", "fail")
    assert sec["phonetic_texture"] in ("pass", "warn", "fail")
    assert sec["rhyme_cadence"] in ("pass", "warn", "fail")
    # LLM-judged skipped
    assert sec["story_sentence"] == "unrun"


def test_validate_runs_llm_when_requested(client):
    fake = {"verdict": "pass", "per_line": []}
    client.post("/songs", json=_payload("v2"))
    with patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake):
        resp = client.post("/songs/v2/validate?include_llm=true")
    assert resp.status_code == 200
    assert resp.json()["sections"][0]["validation"]["story_sentence"] == "pass"


def test_validate_writes_back_to_disk(client, settings):
    client.post("/songs", json=_payload("v3"))
    client.post("/songs/v3/validate?include_llm=false")
    fresh = client.get("/songs/v3").json()
    assert fresh["sections"][0]["validation"]["singability"] in ("pass", "warn", "fail")
```

- [ ] **Step 2: Implement orchestrator**

File: `src/songwriter/api/validation/orchestrator.py`

```python
import json
import sqlite3

from songwriter.api.schemas import Section, Song, SectionValidation
from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.tokenizer import tokenize_line
from songwriter.api.validation import singability, cadence, phonetic_texture, rhyme_cadence, story_sentence


def _load_cadence(db: sqlite3.Connection, slug: str) -> CadencePattern | None:
    row = db.execute(
        "SELECT slug, syllable_template, stress_template, rhyme_compatibility FROM cadence_patterns WHERE slug = ?",
        (slug,),
    ).fetchone()
    if not row:
        return None
    return CadencePattern(
        slug=row["slug"],
        syllable_template=row["syllable_template"] or "?",
        stress_template=row["stress_template"] or "?",
        rhyme_compatibility=json.loads(row["rhyme_compatibility"]) if row["rhyme_compatibility"] else {},
    )


def _worst(verdicts: list[str]) -> str:
    rank = {"fail": 3, "warn": 2, "pass": 1, "unrun": 0}
    return max(verdicts, key=lambda v: rank.get(v, 0))


def validate_song(song: Song, db: sqlite3.Connection, *, include_llm: bool = True) -> Song:
    for section in song.sections:
        cp = _load_cadence(db, section.cadence_pattern)
        ctx = ValidationContext(cadence_pattern=cp, emotion=song.intent.emotion_arc, sub_genre=song.sub_genre)
        line_tokens = [tokenize_line(line, db) for line in section.lyrics]

        per_line_singability = [singability.check_line(toks, ctx) for toks in line_tokens]
        per_line_cadence = [cadence.check_line(toks, ctx) for toks in line_tokens]
        per_line_pt = [phonetic_texture.check_line(toks, ctx) for toks in line_tokens]
        rc_outcome = rhyme_cadence.check_section(line_tokens, ctx)

        warnings: list[str] = []
        for r in per_line_singability + per_line_cadence + per_line_pt + [rc_outcome]:
            warnings.extend(r.warnings)

        story = "unrun"
        if include_llm and section.lyrics:
            story_outcome = story_sentence.check_section(
                section.lyrics, ctx, intent_story=song.intent.story.model_dump()
            )
            story = story_outcome.verdict
            warnings.extend(story_outcome.warnings)

        section.validation = SectionValidation(
            singability=_worst([r.verdict for r in per_line_singability]) if per_line_singability else "unrun",
            cadence=_worst([r.verdict for r in per_line_cadence]) if per_line_cadence else "unrun",
            phonetic_texture=_worst([r.verdict for r in per_line_pt]) if per_line_pt else "unrun",
            rhyme_cadence=rc_outcome.verdict,
            story_sentence=story,
            warnings=warnings,
        )
    return song
```

- [ ] **Step 3: Implement endpoint**

File: `src/songwriter/api/routes/validate.py`

```python
import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from songwriter.api.deps import get_db, get_settings
from songwriter.api.schemas import Song
from songwriter.api.settings import Settings
from songwriter.api.songs_io import path_for_slug, read_song, write_song
from songwriter.api.validation.orchestrator import validate_song


router = APIRouter()


@router.post("/songs/{slug}/validate")
def run_validate(
    slug: str,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    include_llm: bool = Query(True),
) -> Song:
    if not path_for_slug(settings.songs_dir, slug).exists():
        raise HTTPException(404, f"song {slug!r} not found")
    song = read_song(settings.songs_dir, slug)
    song = validate_song(song, db, include_llm=include_llm)
    song.last_modified_by = "api"
    song.modified = datetime.now(timezone.utc)
    write_song(settings.songs_dir, song)
    return song
```

- [ ] **Step 4: Register router. Run, verify PASS. Commit**

```bash
git add src/songwriter/api/validation/orchestrator.py src/songwriter/api/routes/validate.py src/songwriter/api/main.py tests/api/test_validate.py
git commit -m "feat(api): validation orchestrator + POST /songs/{slug}/validate"
```

---

## Task 14: WebSocket connection manager + endpoint

**Files:**
- Create: `src/songwriter/api/ws.py`
- Modify: `src/songwriter/api/routes/songs.py` (add WS endpoint)
- Create: `tests/api/test_ws.py`

The connection manager keeps a `dict[str, set[WebSocket]]` (slug → connections). `connect`, `disconnect`, `broadcast(slug, payload)`. The WS endpoint per-song sends a snapshot on connect, then keeps the connection open for server-pushed updates.

- [ ] **Step 1: Failing test**

File: `tests/api/test_ws.py`

```python
import json


def _payload():
    return {
        "id": "ws1", "title": "WS",
        "genre": "pop", "sub_genre": "alt-pop",
        "intent": {"topic": "t", "emotion_arc": "surrender",
                   "story": {"event": "e", "emotion": "m", "resolution": "r"}},
        "production": {"bpm": 88, "structure_template": "pop.standard", "energy_curve": [0.4]},
        "sections": [],
    }


def test_ws_sends_snapshot_on_connect(client):
    client.post("/songs", json=_payload())
    with client.websocket_connect("/ws/songs/ws1") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot"
        assert msg["song"]["title"] == "WS"


def test_ws_broadcast_on_put(client):
    client.post("/songs", json=_payload())
    with client.websocket_connect("/ws/songs/ws1") as ws:
        ws.receive_json()  # snapshot
        body = _payload()
        body["title"] = "Renamed"
        client.put("/songs/ws1", json=body)
        update = ws.receive_json()
        assert update["type"] == "update"
        assert update["song"]["title"] == "Renamed"
```

- [ ] **Step 2: Implement `ws.py`**

```python
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, slug: str, ws: WebSocket) -> None:
        await ws.accept()
        self._conns[slug].add(ws)

    def disconnect(self, slug: str, ws: WebSocket) -> None:
        self._conns[slug].discard(ws)

    async def broadcast(self, slug: str, payload: Any) -> None:
        dead = []
        for ws in list(self._conns.get(slug, ())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._conns[slug].discard(ws)


manager = ConnectionManager()
```

- [ ] **Step 3: Wire WS endpoint and broadcast on writes**

In `src/songwriter/api/routes/songs.py`:

Add at the top:

```python
from fastapi import WebSocket, WebSocketDisconnect

from songwriter.api.ws import manager
```

After `update_song`, append:

```python
@router.websocket("/ws/songs/{slug}")
async def ws_song(websocket: WebSocket, slug: str):
    settings: Settings = websocket.app.state.settings
    await manager.connect(slug, websocket)
    try:
        try:
            snapshot = read_song(settings.songs_dir, slug)
            await websocket.send_json({"type": "snapshot", "song": snapshot.model_dump(mode="json")})
        except FileNotFoundError:
            await websocket.send_json({"type": "snapshot", "song": None})
        while True:
            await websocket.receive_text()  # keep-alive; clients can send pings
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(slug, websocket)
```

Modify `create_song` and `update_song` to broadcast after the write:

```python
import asyncio

# inside create_song / update_song, after write_song:
asyncio.create_task(manager.broadcast(song.id, {"type": "update", "song": song.model_dump(mode="json")}))
```

(Make both functions `async def` and `await` the broadcast directly instead of `asyncio.create_task` — cleaner. Update the function signature accordingly.)

- [ ] **Step 4: Run, verify PASS. Commit**

```bash
git add src/songwriter/api/ws.py src/songwriter/api/routes/songs.py tests/api/test_ws.py
git commit -m "feat(api): per-song WebSocket with snapshot + broadcast on write"
```

---

## Task 15: File watcher → broadcast bridge

**Files:**
- Create: `src/songwriter/api/watcher.py`
- Modify: `src/songwriter/api/main.py` (start watcher in lifespan)
- Create: `tests/api/test_watcher.py`

The watcher monitors `settings.songs_dir` for `*.json` writes. When a file changes, it reads the file, parses to `Song`, and broadcasts `{"type": "update", "source": "external", "song": ...}` to subscribers of that slug. Suppresses self-echo: the API records its own writes and skips watcher events that happened within ~500ms of a self-write.

- [ ] **Step 1: Failing test**

```python
import asyncio
import time
from pathlib import Path

import pytest

from songwriter.api.watcher import SongFileWatcher
from songwriter.api.ws import ConnectionManager


@pytest.mark.asyncio
async def test_watcher_broadcasts_on_external_write(tmp_path):
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    mgr = ConnectionManager()

    # capture broadcasts
    captured: list[tuple[str, dict]] = []
    async def fake_broadcast(slug, payload):
        captured.append((slug, payload))
    mgr.broadcast = fake_broadcast  # type: ignore

    watcher = SongFileWatcher(songs_dir=songs_dir, manager=mgr)
    watcher.start()
    try:
        # write a valid song JSON externally
        from songwriter.api.schemas import Song, Intent, IntentStory, Production
        song = Song(
            id="ext", title="E", genre="pop", sub_genre="alt-pop",
            intent=Intent(topic="t", emotion_arc="surrender",
                          story=IntentStory(event="e", emotion="m", resolution="r")),
            production=Production(bpm=88, structure_template="pop.standard", energy_curve=[0.4]),
        )
        (songs_dir / "ext.json").write_text(song.model_dump_json())
        # wait for watcher
        for _ in range(40):
            if captured: break
            await asyncio.sleep(0.05)
    finally:
        watcher.stop()

    assert captured, "expected at least one broadcast"
    slug, payload = captured[0]
    assert slug == "ext"
    assert payload["type"] == "update"
    assert payload.get("source") == "external"


def test_self_write_is_suppressed(tmp_path):
    songs_dir = tmp_path / "songs"
    songs_dir.mkdir()
    mgr = ConnectionManager()
    watcher = SongFileWatcher(songs_dir=songs_dir, manager=mgr)
    watcher.note_self_write("self")
    # within suppression window — not "external"
    assert watcher._is_self_write("self") is True
    # outside window
    watcher._self_writes["self"] = time.time() - 10
    assert watcher._is_self_write("self") is False
```

- [ ] **Step 2: Implement `watcher.py`**

```python
import asyncio
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from songwriter.api.schemas import Song
from songwriter.api.ws import ConnectionManager


_SELF_WRITE_WINDOW_S = 0.5


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: "SongFileWatcher") -> None:
        self.watcher = watcher

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.watcher._on_file_event(Path(event.src_path))

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.watcher._on_file_event(Path(event.src_path))


class SongFileWatcher:
    def __init__(self, songs_dir: Path, manager: ConnectionManager,
                 loop: asyncio.AbstractEventLoop | None = None) -> None:
        self.songs_dir = songs_dir
        self.manager = manager
        self.loop = loop
        self._observer = Observer()
        self._self_writes: dict[str, float] = {}

    def start(self) -> None:
        self.songs_dir.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(_Handler(self), str(self.songs_dir), recursive=False)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=2)

    def note_self_write(self, slug: str) -> None:
        self._self_writes[slug] = time.time()

    def _is_self_write(self, slug: str) -> bool:
        ts = self._self_writes.get(slug)
        if ts is None:
            return False
        return (time.time() - ts) < _SELF_WRITE_WINDOW_S

    def _on_file_event(self, path: Path) -> None:
        if path.suffix != ".json":
            return
        slug = path.stem
        if self._is_self_write(slug):
            return
        try:
            song = Song.model_validate_json(path.read_text())
        except Exception:
            return
        payload = {"type": "update", "source": "external", "song": song.model_dump(mode="json")}
        if self.loop is not None:
            asyncio.run_coroutine_threadsafe(self.manager.broadcast(slug, payload), self.loop)
        else:
            # fallback for tests without a running loop
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self.manager.broadcast(slug, payload))
            except RuntimeError:
                asyncio.run(self.manager.broadcast(slug, payload))
```

- [ ] **Step 3: Wire in `main.py` lifespan**

```python
import asyncio
from contextlib import asynccontextmanager

from songwriter.api.watcher import SongFileWatcher
from songwriter.api.ws import manager as ws_manager


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.songs_dir.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        watcher = SongFileWatcher(songs_dir=settings.songs_dir, manager=ws_manager, loop=loop)
        watcher.start()
        app.state.watcher = watcher
        try:
            yield
        finally:
            watcher.stop()
    ...
```

Also update `routes/songs.py` to call `watcher.note_self_write(slug)` immediately before each `write_song(...)`.

- [ ] **Step 4: Run, verify PASS. Commit**

```bash
git add src/songwriter/api/watcher.py src/songwriter/api/main.py src/songwriter/api/routes/songs.py tests/api/test_watcher.py
git commit -m "feat(api): file watcher → broadcast bridge with self-write suppression"
```

---

## Task 16: start.sh + integration test + final verification

**Files:**
- Create: `songwriter/start.sh`
- Create: `tests/api/test_integration.py`

- [ ] **Step 1: `start.sh`**

File: `songwriter/start.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f data/songwriter.db ]; then
  echo "DB missing — running songwriter-build..."
  ./.venv/bin/songwriter-build
fi
exec ./.venv/bin/uvicorn songwriter.api.main:app --reload --port 8000
```

```bash
chmod +x start.sh
```

- [ ] **Step 2: Integration test**

File: `tests/api/test_integration.py`

```python
from unittest.mock import patch


SONG = {
    "id": "integration", "title": "End-to-End",
    "genre": "rnb", "sub_genre": "alt-rnb",
    "intent": {"topic": "late call", "emotion_arc": "surrender",
               "story": {"event": "she calls late", "emotion": "I should know better",
                         "resolution": "I let her in anyway"}},
    "production": {"bpm": 72, "structure_template": "rnb.intimate-confession",
                   "energy_curve": [0.3, 0.7, 0.85]},
    "sections": [{
        "id": "v1", "label": "Verse 1", "lock_state": "draft",
        "cadence_pattern": "melodic-glide",
        "lyrics": ["you called me late", "said you couldn't sleep"],
    }],
}


def test_full_lifecycle(client, settings):
    # 1. create
    r = client.post("/songs", json=SONG)
    assert r.status_code == 201

    # 2. live snapshot via WS
    with client.websocket_connect("/ws/songs/integration") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"

        # 3. validate (deterministic only — keep test fast & offline)
        rv = client.post("/songs/integration/validate?include_llm=false")
        assert rv.status_code == 200

        # 4. WS receives an update
        update = ws.receive_json()
        assert update["type"] == "update"
        sec = update["song"]["sections"][0]
        for k in ("singability", "cadence", "phonetic_texture", "rhyme_cadence"):
            assert sec["validation"][k] in ("pass", "warn", "fail")

    # 5. on disk, validation results persisted
    fresh = client.get("/songs/integration").json()
    assert fresh["sections"][0]["validation"]["singability"] in ("pass", "warn", "fail")


def test_descriptor_cache_round_trip(client):
    # seeded entries are pinned; first call to a seeded one increments use_count
    r1 = client.get("/descriptors/Frank%20Ocean")
    assert r1.status_code == 200
    assert r1.json()["source"] == "user-curated"

    # auto-LLM path on a fresh name
    fake = {
        "descriptor_short": "Smooth tenor with bright lead.",
        "descriptor_long": "Smooth tenor lead. Production is clean and bright with tight live drums and warm Rhodes pads. " * 3,
        "vocal_attributes": {"range": "tenor"}, "production_attrs": {"tempo_zone": "80-100"},
        "genre_context": "alt-rnb",
    }
    with patch("songwriter.api.routes.descriptors.ask_claude_json", return_value=fake):
        r2 = client.get("/descriptors/Some%20New%20Person")
    assert r2.status_code == 200
    assert r2.json()["source"] == "auto-llm"
    assert r2.json()["quality_state"] == "unverified"
```

- [ ] **Step 3: Run full suite**

```bash
pytest -q
```

Expected: every test from this plan + every test from the data-layer plan passes (148 from data layer + new API tests).

- [ ] **Step 4: Manual smoke test (optional but recommended)**

```bash
./start.sh &  # in one terminal
curl -s http://localhost:8000/healthz | python -m json.tool
curl -s http://localhost:8000/genres | python -m json.tool | head -40
curl -s 'http://localhost:8000/rhymes?word=love&limit=5' | python -m json.tool
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add start.sh tests/api/test_integration.py
chmod +x start.sh
git commit -m "feat(api): start.sh + end-to-end integration test"
```

---

## Self-review summary

**Spec coverage (FastAPI scope):**

| Spec deliverable | Task |
|---|---|
| FastAPI app + healthcheck | 1 |
| LLM bridge (`claude --print` for zero-cost AI) | 2 |
| DB-connection dependency | 3 |
| Lookup endpoints (genres, vocab, words, rhymes, burn list) | 4 |
| Production fingerprint + emotion-tempo + structure-template endpoints | 5 |
| Songwriter profile endpoints | 6 |
| Sonic descriptor cache + auto-LLM-on-miss + burn-list scrub | 7 |
| Pydantic song schemas (cross-plan contract) | 8 |
| Song JSON IO + CRUD endpoints | 9 |
| Validation tokenizer + DB phonetic resolver | 10 |
| 4 deterministic validation engines | 11 |
| LLM-judged Story/Sentence engine | 12 |
| Validation orchestrator + endpoint | 13 |
| WebSocket snapshot + broadcast | 14 |
| File watcher with self-write suppression | 15 |
| start.sh + integration test | 16 |

**Decisions baked in (recap):**
- LLM calls use `claude --print` subprocess; the API never imports `anthropic`.
- `include_llm` query param on `/validate` lets the UI run cheap deterministic checks on save and the LLM-judged check on demand.
- Descriptor cache auto-LLM on miss, scrub against burn list, mark `quality_state='unverified'` for later review.
- Self-write suppression on the watcher prevents the round-trip echo when the API itself writes a song JSON.

**Out of scope (sister plans):**
- Claude Code skill — calls these endpoints from `/song draft`, `/song validate`, etc. Skill plan is next.
- Web UI — consumes endpoints + WebSocket. UI plan is last.

**Critical assertions tested:**
- Healthcheck returns settings-driven paths.
- Lookup endpoints return DB-backed data; 404 on unknown slugs.
- Descriptor cache: HIT increments use_count, MISS calls LLM, burn-list words get scrubbed, normalization handles "The" honorific.
- Song CRUD round-trips through disk; atomic writes leave no `.tmp` orphans.
- Validation orchestrator runs all 4 deterministic engines, optionally adds LLM-judged engine, writes results into JSON.
- WebSocket sends snapshot on connect, broadcast on PUT.
- File watcher broadcasts external writes but suppresses self-writes within 500ms.

**Type/name consistency:**
- Validation engines all expose `check_line(tokens, ctx) -> RuleOutcome` (Singability, Cadence, Phonetic Texture) or `check_section(line_tokens, ctx) -> RuleOutcome` (Rhyme-Cadence) or `check_section(lyrics, ctx, *, intent_story) -> RuleOutcome` (Story/Sentence — different signature because LLM input is raw lyrics).
- `RuleOutcome` is `(verdict: "pass"|"warn"|"fail", warnings: list[str])` consistently.
- `RuleResult` (in `schemas.py`) adds `"unrun"` for results that haven't been computed yet — the orchestrator writes either a real verdict or leaves `"unrun"`.
- DB connection injected via `get_db` dependency throughout.

---

## Execution handoff

This plan is structured for subagent-driven execution. 16 tasks, mostly Python with no big content YAMLs. Tighter than the data-layer plan (~2400 lines vs ~5500). One commit per task; full suite passes after every commit.

After execution, sister plans:
- `2026-MM-DD-songwriter-skill.md` — uses these endpoints from the `/song` skill
- `2026-MM-DD-songwriter-web-ui.md` — Next.js client consuming the endpoints + WebSocket
