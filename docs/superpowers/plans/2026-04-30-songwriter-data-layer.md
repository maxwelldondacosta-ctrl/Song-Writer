# Songwriter Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible pipeline that compiles open-source phonetic data (CMUdict + gruut) plus human-editable YAML seed files into `data/songwriter.db`, fully populated for Phase 1's two ship genres (Pop + R&B).

**Architecture:** A standalone Python package (`src/songwriter/seeds/`) that owns DB schema, phonetic derivations, and YAML→SQL compilation. SQLite is the build output; YAML is the source of truth for hand-tagged content; CMUdict + gruut are the source of truth for the ~135K-row phonetic master index. The build script is idempotent — running it twice produces the same DB.

**Tech Stack:** Python 3.12, SQLite (stdlib), pyyaml, gruut, requests, pytest. Pip-installable via `pyproject.toml`. No FastAPI in this plan — the API layer consumes this DB but lives in a separate sub-plan.

**Scope boundary:** This plan ships the DB only. It does not ship API endpoints, validation rule engines that run in production, the Claude Code skill, or the web UI. Those are separate sub-plans.

**Sister plans (not yet written):**
- `2026-MM-DD-songwriter-fastapi.md` — backend service, validation engines, websocket file-watcher
- `2026-MM-DD-songwriter-skill.md` — Claude Code `/song` skill, 7-step workflow, prompt refinement, descriptor cache
- `2026-MM-DD-songwriter-web-ui.md` — Next.js home, wizard, song editor, live JSON sync

---

## File Structure

```
songwriter/                                    # repo root
├── pyproject.toml                             # Python project + deps
├── .gitignore                                 # ignores .venv, data/songwriter.db, data/cache/
├── README.md                                  # repo overview (data-layer-only for now)
├── src/
│   └── songwriter/
│       ├── __init__.py
│       └── seeds/
│           ├── __init__.py
│           ├── build.py                       # top-level orchestrator (CLI entry)
│           ├── db.py                          # SQLite connection + schema apply
│           ├── cmudict.py                     # download, cache, parse CMUdict
│           ├── arpabet_ipa.py                 # ARPAbet → IPA mapping table + fn
│           ├── phonemes.py                    # phoneme classification (vowel/consonant/hard/soft)
│           ├── derived.py                     # derive syllables, stress, rhyme class, vowel shape, attack, density
│           ├── gruut_fallback.py              # IPA via gruut for words missing from CMUdict
│           ├── yaml_loader.py                 # load + validate YAML seed files
│           └── seeders/
│               ├── __init__.py
│               ├── words.py                   # CMUdict + gruut → words table
│               ├── genres.py                  # genres.yml + sub-genre tree → DB
│               ├── cadence_patterns.py
│               ├── structure_templates.py
│               ├── production_fingerprints.py
│               ├── emotion_tempo_map.py
│               ├── burn_list.py
│               ├── vocab_banks.py             # data/vocab/**/*.yml → DB
│               ├── songwriter_profiles.py     # data/songwriters/**/*.yml → DB
│               └── sonic_descriptors.py       # data/descriptors/*.yml → DB
├── tests/
│   ├── __init__.py
│   ├── conftest.py                            # pytest fixtures (in-memory DB, sample YAML)
│   ├── test_db.py
│   ├── test_arpabet_ipa.py
│   ├── test_cmudict.py
│   ├── test_phonemes.py
│   ├── test_derived.py
│   ├── test_gruut_fallback.py
│   ├── test_yaml_loader.py
│   ├── test_seeder_words.py
│   ├── test_seeder_genres.py
│   ├── test_seeder_cadence.py
│   ├── test_seeder_structure.py
│   ├── test_seeder_production.py
│   ├── test_seeder_emotion_tempo.py
│   ├── test_seeder_burn_list.py
│   ├── test_seeder_vocab.py
│   ├── test_seeder_songwriters.py
│   ├── test_seeder_descriptors.py
│   └── test_build_integration.py              # full end-to-end build
└── data/
    ├── schema.sql                             # DDL
    ├── genres.yml
    ├── cadence_patterns.yml
    ├── structure_templates.yml
    ├── production_fingerprints.yml
    ├── emotion_tempo_map.yml
    ├── burn_list.yml
    ├── vocab/
    │   ├── pop/
    │   │   ├── confession.yml
    │   │   ├── infatuation.yml
    │   │   ├── breakup.yml
    │   │   ├── party.yml
    │   │   ├── nostalgia.yml
    │   │   └── empowerment.yml
    │   └── rnb/
    │       ├── intimacy.yml
    │       ├── longing.yml
    │       ├── seduction.yml
    │       ├── heartbreak.yml
    │       ├── late-night.yml
    │       └── devotion.yml
    ├── songwriters/
    │   ├── pop/
    │   │   ├── diane-warren.yml
    │   │   ├── max-martin.yml
    │   │   ├── julia-michaels.yml
    │   │   ├── finneas.yml
    │   │   └── sia.yml
    │   └── rnb/
    │       ├── frank-ocean.yml
    │       ├── the-dream.yml
    │       ├── babyface.yml
    │       ├── rodney-jerkins.yml
    │       └── jam-and-lewis.yml
    ├── descriptors/
    │   └── seeded.yml                         # ~10 pre-seeded descriptors
    ├── cache/                                 # gitignored, holds CMUdict download
    └── songwriter.db                          # built artifact, gitignored
```

---

## Conventions used in every task

- TDD: write the failing test first, run it, implement minimal code, run again, commit.
- Every Python file gets a corresponding test file. One test file per module.
- Pytest discovers via `tests/`. Fixtures in `tests/conftest.py`.
- Commit message format: `feat(data): <subject>` for additions, `chore(data): <subject>` for plumbing, `test(data): <subject>` for test-only changes.
- Run all tests after each task with `pytest -q` to catch regressions.
- All paths in code are relative to repo root resolved via a `REPO_ROOT` constant in `seeds/__init__.py` so tests can override.

---

## Task 1: Python project scaffolding

**Files:**
- Create: `songwriter/pyproject.toml`
- Create: `songwriter/.gitignore`
- Create: `songwriter/README.md`
- Create: `songwriter/src/songwriter/__init__.py`
- Create: `songwriter/src/songwriter/seeds/__init__.py`
- Create: `songwriter/src/songwriter/seeds/seeders/__init__.py`
- Create: `songwriter/tests/__init__.py`
- Create: `songwriter/tests/conftest.py`

- [ ] **Step 1: Create the repo root and `cd` into it**

```bash
mkdir -p "/Users/mdacosta/Desktop/Song Writing/songwriter"
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
git init -b main
```

- [ ] **Step 2: Write `pyproject.toml`**

File: `songwriter/pyproject.toml`

```toml
[project]
name = "songwriter"
version = "0.1.0"
description = "Songwriter app data layer + build pipeline"
requires-python = ">=3.12"
dependencies = [
  "pyyaml>=6.0",
  "gruut[en]>=2.4",
  "requests>=2.31",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-cov>=5.0",
]

[project.scripts]
songwriter-build = "songwriter.seeds.build:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/songwriter"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra"
```

- [ ] **Step 3: Write `.gitignore`**

File: `songwriter/.gitignore`

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.coverage
data/cache/
data/songwriter.db
.DS_Store
```

- [ ] **Step 4: Write minimal `README.md`**

File: `songwriter/README.md`

```markdown
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
```

- [ ] **Step 5: Create empty package files**

```bash
mkdir -p src/songwriter/seeds/seeders
mkdir -p tests
touch src/songwriter/__init__.py
touch src/songwriter/seeds/__init__.py
touch src/songwriter/seeds/seeders/__init__.py
touch tests/__init__.py
```

- [ ] **Step 6: Write `seeds/__init__.py` with `REPO_ROOT`**

File: `songwriter/src/songwriter/seeds/__init__.py`

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "songwriter.db"
SCHEMA_PATH = DATA_DIR / "schema.sql"
```

- [ ] **Step 7: Write `tests/conftest.py` with shared fixtures**

File: `songwriter/tests/conftest.py`

```python
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def in_memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    (d / "cache").mkdir()
    return d
```

- [ ] **Step 8: Create venv, install, verify pytest discovers zero tests**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Expected: `no tests ran` (exit 5). That's fine — confirms pytest is wired up.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .gitignore README.md src tests
git commit -m "chore(data): scaffold python project + pytest"
```

---

## Task 2: SQLite schema DDL

**Files:**
- Create: `songwriter/data/schema.sql`
- Create: `songwriter/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

File: `songwriter/tests/test_db.py`

```python
import sqlite3
from pathlib import Path

from songwriter.seeds import SCHEMA_PATH


EXPECTED_TABLES = {
    "words",
    "vocab_banks",
    "vocab_bank_words",
    "genres",
    "sub_genres",
    "cadence_patterns",
    "songwriter_profiles",
    "artist_descriptor_cache",
    "suno_burn_list",
    "structure_templates",
    "emotion_tempo_map",
    "production_fingerprints",
}


def test_schema_creates_all_expected_tables():
    sql = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    actual = {r[0] for r in rows}
    missing = EXPECTED_TABLES - actual
    assert not missing, f"missing tables: {missing}"


def test_words_table_has_expected_columns():
    sql = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(words)")}
    expected = {
        "id", "word", "language", "ipa", "arpabet",
        "syllables", "stress_pattern", "rhyme_class",
        "vowel_shape", "first_syllable_attack",
        "consonant_density", "syllable_count_class",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_db.py -v
```

Expected: FAIL — `schema.sql` does not exist.

- [ ] **Step 3: Write `data/schema.sql`**

File: `songwriter/data/schema.sql`

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE words (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  word                  TEXT NOT NULL,
  language              TEXT NOT NULL DEFAULT 'en',
  ipa                   TEXT,
  arpabet               TEXT,
  syllables             INTEGER,
  stress_pattern        TEXT,
  rhyme_class           TEXT,
  vowel_shape           TEXT,
  first_syllable_attack TEXT,
  consonant_density     REAL,
  syllable_count_class  TEXT,
  UNIQUE(word, language)
);
CREATE INDEX idx_words_word ON words(word);
CREATE INDEX idx_words_rhyme_class ON words(rhyme_class);
CREATE INDEX idx_words_vowel_shape ON words(vowel_shape);

CREATE TABLE genres (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                TEXT UNIQUE NOT NULL,
  name                TEXT NOT NULL,
  parent_genre_id     INTEGER REFERENCES genres(id),
  description         TEXT,
  typical_bpm_min     INTEGER,
  typical_bpm_max     INTEGER,
  default_structure_id INTEGER,
  notes_for_suno      TEXT
);

CREATE TABLE sub_genres (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  genre_id            INTEGER NOT NULL REFERENCES genres(id),
  slug                TEXT NOT NULL,
  name                TEXT NOT NULL,
  description         TEXT,
  typical_bpm_min     INTEGER,
  typical_bpm_max     INTEGER,
  default_structure_id INTEGER,
  notes_for_suno      TEXT,
  UNIQUE(genre_id, slug)
);
CREATE INDEX idx_sub_genres_genre ON sub_genres(genre_id);

CREATE TABLE vocab_banks (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  slug            TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  description     TEXT,
  parent_bank_id  INTEGER REFERENCES vocab_banks(id)
);

CREATE TABLE vocab_bank_words (
  bank_id           INTEGER NOT NULL REFERENCES vocab_banks(id),
  word_id           INTEGER NOT NULL REFERENCES words(id),
  emotional_weight  REAL,
  imagery_class     TEXT,
  cliche_flag       INTEGER NOT NULL DEFAULT 0,
  ai_bias_flag      INTEGER NOT NULL DEFAULT 0,
  notes             TEXT,
  PRIMARY KEY (bank_id, word_id)
);

CREATE TABLE cadence_patterns (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                TEXT UNIQUE NOT NULL,
  name                TEXT NOT NULL,
  syllable_template   TEXT,
  stress_template     TEXT,
  typical_genres      TEXT,   -- JSON array of genre slugs
  example_lines       TEXT,   -- JSON array
  rhyme_compatibility TEXT    -- JSON object
);

CREATE TABLE songwriter_profiles (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                  TEXT UNIQUE NOT NULL,
  display_name          TEXT NOT NULL,
  real_name             TEXT,
  era                   TEXT,
  primary_genre_id      INTEGER REFERENCES genres(id),
  role                  TEXT NOT NULL CHECK (role IN
                          ('pure-songwriter','producer-songwriter','singer-songwriter','self-writing-artist')),
  sub_genres            TEXT,   -- JSON
  notable_credits       TEXT,   -- JSON
  craft_signature       TEXT,   -- JSON
  personality_traits    TEXT,   -- JSON
  writing_style         TEXT,   -- JSON
  preferred_cadences    TEXT,   -- JSON of cadence_pattern slugs
  vocab_fingerprint     TEXT,   -- JSON
  phonetic_fingerprint  TEXT,   -- JSON
  structure_preferences TEXT,   -- JSON
  hook_style            TEXT,
  reference_tracks      TEXT,   -- JSON (titles only)
  adoption_prompt       TEXT NOT NULL
);

CREATE TABLE artist_descriptor_cache (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  normalized_name   TEXT UNIQUE NOT NULL,
  canonical_name    TEXT NOT NULL,
  era_label         TEXT,
  descriptor        TEXT NOT NULL,
  descriptor_short  TEXT NOT NULL,
  descriptor_long   TEXT NOT NULL,
  vocal_attributes  TEXT,   -- JSON
  production_attrs  TEXT,   -- JSON
  genre_context     TEXT,
  source            TEXT NOT NULL CHECK (source IN
                      ('auto-llm','songwriter-profile-derived','user-curated')),
  quality_state     TEXT NOT NULL DEFAULT 'unverified'
                      CHECK (quality_state IN ('unverified','reviewed','pinned')),
  use_count         INTEGER NOT NULL DEFAULT 0,
  created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at      TEXT
);

CREATE TABLE suno_burn_list (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  word          TEXT UNIQUE NOT NULL,
  severity      TEXT NOT NULL CHECK (severity IN ('mild','strong','extreme')),
  drift_direction TEXT,
  alternatives  TEXT   -- JSON array
);

CREATE TABLE structure_templates (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                TEXT UNIQUE NOT NULL,
  name                TEXT NOT NULL,
  sections            TEXT NOT NULL,   -- JSON array of {section, energy, syllable_target}
  genre_compatibility TEXT             -- JSON array of genre/sub-genre slugs
);

CREATE TABLE emotion_tempo_map (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  emotion       TEXT NOT NULL,
  sub_genre_id  INTEGER NOT NULL REFERENCES sub_genres(id),
  bpm_min       INTEGER NOT NULL,
  bpm_max       INTEGER NOT NULL,
  energy_curve  TEXT,   -- JSON array of floats
  anti_prompts  TEXT,   -- JSON array
  UNIQUE(emotion, sub_genre_id)
);

CREATE TABLE production_fingerprints (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  sub_genre_id          INTEGER UNIQUE NOT NULL REFERENCES sub_genres(id),
  instrumentation       TEXT,   -- JSON
  vocal_style           TEXT,   -- JSON
  mix_attributes        TEXT,   -- JSON
  positive_descriptors  TEXT,   -- JSON
  negative_descriptors  TEXT    -- JSON
);
```

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest tests/test_db.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add data/schema.sql tests/test_db.py
git commit -m "feat(data): add SQLite schema for all Phase 1 tables"
```

---

## Task 3: DB initialization helper

**Files:**
- Create: `songwriter/src/songwriter/seeds/db.py`
- Modify: `songwriter/tests/test_db.py`

- [ ] **Step 1: Add a failing test for `init_db`**

Append to: `songwriter/tests/test_db.py`

```python
from songwriter.seeds import db as db_module


def test_init_db_creates_file_with_tables(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    assert target.exists()
    import sqlite3
    conn = sqlite3.connect(target)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert "words" in names
    assert "songwriter_profiles" in names


def test_init_db_is_idempotent(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    db_module.init_db(target)  # should not raise
    assert target.exists()


def test_connect_returns_row_factory(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    conn = db_module.connect(target)
    row = conn.execute("SELECT 1 AS x").fetchone()
    assert row["x"] == 1
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_db.py -v
```

Expected: 3 NEW failures (`db_module` has no attribute `init_db`).

- [ ] **Step 3: Implement `db.py`**

File: `songwriter/src/songwriter/seeds/db.py`

```python
import sqlite3
from pathlib import Path

from songwriter.seeds import SCHEMA_PATH


def init_db(path: Path) -> None:
    """Drop and recreate the DB at `path`, applying the full schema."""
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    sql = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/db.py tests/test_db.py
git commit -m "feat(data): add init_db and connect helpers"
```

---

## Task 4: ARPAbet → IPA mapping

**Files:**
- Create: `songwriter/src/songwriter/seeds/arpabet_ipa.py`
- Create: `songwriter/tests/test_arpabet_ipa.py`

- [ ] **Step 1: Write the failing test**

File: `songwriter/tests/test_arpabet_ipa.py`

```python
import pytest

from songwriter.seeds.arpabet_ipa import arpabet_to_ipa, strip_stress


@pytest.mark.parametrize("arpabet,ipa", [
    ("L AH1 V",       "lʌv"),         # love
    ("HH AA1 R T",    "hɑrt"),        # heart
    ("AH0 B AH1 V",   "əbʌv"),        # above
    ("S T AO1 R M",   "stɔrm"),       # storm
    ("M AY1 N D",     "maɪnd"),       # mind
    ("B IY1",         "bi"),          # bee
    ("CH OY1 S",      "tʃɔɪs"),       # choice
    ("ER1",           "ɝ"),           # stressed schwa-r
    ("B AH0 T ER0",   "bətɚ"),        # butter (unstressed ER → ɚ)
])
def test_arpabet_to_ipa_known_words(arpabet, ipa):
    assert arpabet_to_ipa(arpabet) == ipa


def test_strip_stress_removes_digits():
    assert strip_stress("AH1") == "AH"
    assert strip_stress("AH0") == "AH"
    assert strip_stress("ER2") == "ER"
    assert strip_stress("B") == "B"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_arpabet_ipa.py -v
```

Expected: all FAIL — module does not exist.

- [ ] **Step 3: Implement `arpabet_ipa.py`**

File: `songwriter/src/songwriter/seeds/arpabet_ipa.py`

```python
"""ARPAbet → IPA. Stress-aware for AH and ER (schwa vs wedge).

CMUdict ARPAbet uses 0/1/2 stress digits on vowels (0=unstressed, 1=primary, 2=secondary).
We use those digits to choose between schwa-family vs full-vowel IPA where it matters.
"""

# Stress-conditional vowel mapping: (stressed_form, unstressed_form)
_STRESS_CONDITIONAL = {
    "AH": ("ʌ", "ə"),
    "ER": ("ɝ", "ɚ"),
}

# Stress-invariant phoneme mapping
_BASE = {
    # Vowels
    "AA": "ɑ",
    "AE": "æ",
    "AO": "ɔ",
    "AW": "aʊ",
    "AY": "aɪ",
    "EH": "ɛ",
    "EY": "eɪ",
    "IH": "ɪ",
    "IY": "i",
    "OW": "oʊ",
    "OY": "ɔɪ",
    "UH": "ʊ",
    "UW": "u",
    # Consonants
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ",
    "K": "k", "L": "l", "M": "m", "N": "n",
    "NG": "ŋ", "P": "p", "R": "r", "S": "s",
    "SH": "ʃ", "T": "t", "TH": "θ", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}


def strip_stress(token: str) -> str:
    """Remove a trailing stress digit (0/1/2) from a phoneme token."""
    if token and token[-1].isdigit():
        return token[:-1]
    return token


def _phoneme_to_ipa(token: str) -> str:
    bare = strip_stress(token)
    if bare in _STRESS_CONDITIONAL:
        stressed, unstressed = _STRESS_CONDITIONAL[bare]
        # token had trailing digit if and only if vowel
        if token != bare and token[-1] == "0":
            return unstressed
        return stressed
    return _BASE.get(bare, "")


def arpabet_to_ipa(arpabet: str) -> str:
    """Convert a space-separated ARPAbet string to an IPA string."""
    return "".join(_phoneme_to_ipa(t) for t in arpabet.split())
```

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest tests/test_arpabet_ipa.py -v
```

Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/arpabet_ipa.py tests/test_arpabet_ipa.py
git commit -m "feat(data): add stress-aware ARPAbet→IPA mapping"
```

---

## Task 5: Phoneme classification helpers

**Files:**
- Create: `songwriter/src/songwriter/seeds/phonemes.py`
- Create: `songwriter/tests/test_phonemes.py`

These helpers classify phonemes for downstream derivations (rhyme class, attack profile, consonant density). They operate on bare ARPAbet (stress-stripped).

- [ ] **Step 1: Write the failing test**

File: `songwriter/tests/test_phonemes.py`

```python
import pytest

from songwriter.seeds.phonemes import (
    is_vowel,
    is_consonant,
    attack_class,
    is_hard_consonant,
    vowel_shape_label,
)


@pytest.mark.parametrize("ph", ["AA", "AH", "AY", "ER", "OW"])
def test_is_vowel_true(ph):
    assert is_vowel(ph) is True


@pytest.mark.parametrize("ph", ["B", "CH", "DH", "S", "ZH"])
def test_is_vowel_false(ph):
    assert is_vowel(ph) is False
    assert is_consonant(ph) is True


@pytest.mark.parametrize("ph,expected", [
    ("P", "hard"), ("T", "hard"), ("K", "hard"),
    ("B", "hard"), ("D", "hard"), ("G", "hard"),
    ("CH", "hard"), ("JH", "hard"),
    ("F", "hard"), ("S", "hard"), ("SH", "hard"), ("TH", "hard"), ("HH", "hard"),
    ("M", "soft"), ("N", "soft"), ("NG", "soft"),
    ("L", "soft"), ("R", "soft"), ("W", "soft"), ("Y", "soft"),
    ("V", "soft"), ("Z", "soft"), ("ZH", "soft"), ("DH", "soft"),
    ("AA", "vowel"), ("IY", "vowel"), ("AY", "vowel"),
])
def test_attack_class(ph, expected):
    assert attack_class(ph) == expected


def test_is_hard_consonant_matches_attack():
    assert is_hard_consonant("P") is True
    assert is_hard_consonant("L") is False
    assert is_hard_consonant("AA") is False  # vowels are not "hard consonants"


@pytest.mark.parametrize("ph,expected", [
    ("AE", "short-A"), ("AA", "short-A-back"),
    ("EH", "short-E"), ("IH", "short-I"),
    ("AH", "short-U"), ("UH", "short-OO"),
    ("AO", "short-AW"),
    ("IY", "long-E"), ("UW", "long-U"),
    ("ER", "rhotic"),
    ("AY", "diphthong-AI"), ("AW", "diphthong-AU"),
    ("OY", "diphthong-OI"), ("EY", "diphthong-EI"),
    ("OW", "diphthong-OU"),
])
def test_vowel_shape_label(ph, expected):
    assert vowel_shape_label(ph) == expected
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_phonemes.py -v
```

Expected: all FAIL — module does not exist.

- [ ] **Step 3: Implement `phonemes.py`**

File: `songwriter/src/songwriter/seeds/phonemes.py`

```python
"""Phoneme classification on bare ARPAbet (stress-stripped)."""

VOWELS = {
    "AA", "AE", "AH", "AO", "AW", "AY",
    "EH", "ER", "EY",
    "IH", "IY",
    "OW", "OY",
    "UH", "UW",
}

# Stops, affricates, and voiceless fricatives = "hard"
HARD_CONSONANTS = {
    "P", "T", "K", "B", "D", "G",
    "CH", "JH",
    "F", "S", "SH", "TH", "HH",
}

# Sonorants and voiced fricatives = "soft"
SOFT_CONSONANTS = {
    "M", "N", "NG", "L", "R", "W", "Y",
    "V", "Z", "ZH", "DH",
}

VOWEL_SHAPE = {
    "AE": "short-A",
    "AA": "short-A-back",
    "EH": "short-E",
    "IH": "short-I",
    "AH": "short-U",
    "UH": "short-OO",
    "AO": "short-AW",
    "IY": "long-E",
    "UW": "long-U",
    "ER": "rhotic",
    "AY": "diphthong-AI",
    "AW": "diphthong-AU",
    "OY": "diphthong-OI",
    "EY": "diphthong-EI",
    "OW": "diphthong-OU",
}


def is_vowel(phoneme: str) -> bool:
    return phoneme in VOWELS


def is_consonant(phoneme: str) -> bool:
    return phoneme in HARD_CONSONANTS or phoneme in SOFT_CONSONANTS


def is_hard_consonant(phoneme: str) -> bool:
    return phoneme in HARD_CONSONANTS


def attack_class(phoneme: str) -> str:
    if is_vowel(phoneme):
        return "vowel"
    if phoneme in HARD_CONSONANTS:
        return "hard"
    if phoneme in SOFT_CONSONANTS:
        return "soft"
    raise ValueError(f"unknown phoneme: {phoneme!r}")


def vowel_shape_label(phoneme: str) -> str:
    if phoneme not in VOWEL_SHAPE:
        raise ValueError(f"not a vowel or unsupported: {phoneme!r}")
    return VOWEL_SHAPE[phoneme]
```

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest tests/test_phonemes.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/phonemes.py tests/test_phonemes.py
git commit -m "feat(data): add phoneme classification helpers"
```

---

## Task 6: Derived phonetic fields — syllables, stress pattern

**Files:**
- Create: `songwriter/src/songwriter/seeds/derived.py`
- Create: `songwriter/tests/test_derived.py`

- [ ] **Step 1: Write the failing test**

File: `songwriter/tests/test_derived.py`

```python
import pytest

from songwriter.seeds.derived import (
    syllable_count,
    syllable_count_class,
    stress_pattern,
)


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V", 1),                # love
    ("HH AA1 R T", 1),             # heart
    ("AH0 B AH1 V", 2),            # above
    ("B AH0 T ER0", 2),            # butter
    ("UH0 N D ER0 S T AE1 N D", 3),# understand
])
def test_syllable_count(arpabet, expected):
    assert syllable_count(arpabet) == expected


@pytest.mark.parametrize("count,cls", [
    (1, "mono"),
    (2, "bi"),
    (3, "multi"),
    (4, "multi"),
])
def test_syllable_count_class(count, cls):
    assert syllable_count_class(count) == cls


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V", "1"),              # love (stressed monosyllable)
    ("AH0 B AH1 V", "01"),         # above (unstressed-stressed)
    ("B AH0 T ER0", "00"),         # butter (both unstressed; rare CMUdict edge)
    ("UH0 N D ER0 S T AE1 N D", "001"),  # understand
])
def test_stress_pattern(arpabet, expected):
    assert stress_pattern(arpabet) == expected
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_derived.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement initial `derived.py`**

File: `songwriter/src/songwriter/seeds/derived.py`

```python
"""Derive phonetic fields from CMUdict-style ARPAbet strings."""

from songwriter.seeds.phonemes import is_vowel
from songwriter.seeds.arpabet_ipa import strip_stress


def _tokens(arpabet: str) -> list[str]:
    return [t for t in arpabet.split() if t]


def syllable_count(arpabet: str) -> int:
    """Count syllables = count vowel phonemes (after stripping stress digits)."""
    return sum(1 for t in _tokens(arpabet) if is_vowel(strip_stress(t)))


def syllable_count_class(n: int) -> str:
    if n <= 1:
        return "mono"
    if n == 2:
        return "bi"
    return "multi"


def stress_pattern(arpabet: str) -> str:
    """Concatenate stress digits of vowels in order. Treat 2 as 1 (any stress)."""
    out = []
    for t in _tokens(arpabet):
        bare = strip_stress(t)
        if not is_vowel(bare):
            continue
        digit = t[-1] if t[-1].isdigit() else "0"
        out.append("1" if digit in {"1", "2"} else "0")
    return "".join(out)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_derived.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/derived.py tests/test_derived.py
git commit -m "feat(data): derive syllable count + stress pattern"
```

---

## Task 7: Derived phonetic fields — rhyme class, vowel shape

**Files:**
- Modify: `songwriter/src/songwriter/seeds/derived.py`
- Modify: `songwriter/tests/test_derived.py`

The rhyme class is "everything from the last stressed vowel onward" — the standard rime-based rhyme key. Two words rhyme iff they share this key.

- [ ] **Step 1: Write the failing test (append to existing file)**

Append to: `songwriter/tests/test_derived.py`

```python
from songwriter.seeds.derived import rhyme_class, vowel_shape


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V",       "AH-V"),         # love
    ("AH0 B AH1 V",   "AH-V"),         # above (rhymes with love)
    ("HH AA1 R T",    "AA-R-T"),       # heart
    ("S T AA1 R T",   "AA-R-T"),       # start (rhymes with heart)
    ("M AY1 N D",     "AY-N-D"),       # mind
    ("B IY1",         "IY"),           # bee
    ("M IY1",         "IY"),           # me
    ("B AH0 T ER0",   "ER"),           # butter (no primary stress falls back to last vowel)
])
def test_rhyme_class(arpabet, expected):
    assert rhyme_class(arpabet) == expected


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V",       "short-U"),
    ("HH AA1 R T",    "short-A-back"),
    ("M AY1 N D",     "diphthong-AI"),
    ("B IY1",         "long-E"),
    ("S T AO1 R M",   "short-AW"),
])
def test_vowel_shape(arpabet, expected):
    assert vowel_shape(arpabet) == expected
```

- [ ] **Step 2: Run test, verify the new tests fail**

```bash
pytest tests/test_derived.py -v
```

Expected: 13 NEW failures.

- [ ] **Step 3: Add `rhyme_class` and `vowel_shape` to `derived.py`**

Append to: `songwriter/src/songwriter/seeds/derived.py`

```python
from songwriter.seeds.phonemes import vowel_shape_label


def _last_stressed_vowel_index(tokens: list[str]) -> int | None:
    """Return index of the last vowel with primary or secondary stress.
    Falls back to the last vowel if no stressed vowel found."""
    last_any_vowel = None
    last_stressed = None
    for i, t in enumerate(tokens):
        bare = strip_stress(t)
        if not is_vowel(bare):
            continue
        last_any_vowel = i
        if t[-1] in {"1", "2"}:
            last_stressed = i
    return last_stressed if last_stressed is not None else last_any_vowel


def rhyme_class(arpabet: str) -> str:
    """Rhyme key: bare phonemes from the last stressed vowel to end, joined by '-'."""
    tokens = _tokens(arpabet)
    idx = _last_stressed_vowel_index(tokens)
    if idx is None:
        return ""
    bare = [strip_stress(t) for t in tokens[idx:]]
    return "-".join(bare)


def vowel_shape(arpabet: str) -> str:
    """Vowel-shape label of the last stressed vowel."""
    tokens = _tokens(arpabet)
    idx = _last_stressed_vowel_index(tokens)
    if idx is None:
        return ""
    return vowel_shape_label(strip_stress(tokens[idx]))
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_derived.py -v
```

Expected: all PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/derived.py tests/test_derived.py
git commit -m "feat(data): derive rhyme class + vowel shape"
```

---

## Task 8: Derived phonetic fields — first-syllable attack, consonant density

**Files:**
- Modify: `songwriter/src/songwriter/seeds/derived.py`
- Modify: `songwriter/tests/test_derived.py`

- [ ] **Step 1: Write the failing test**

Append to: `songwriter/tests/test_derived.py`

```python
from songwriter.seeds.derived import first_syllable_attack, consonant_density


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V",       "soft"),    # L (sonorant)
    ("HH AA1 R T",    "hard"),    # HH (voiceless fricative)
    ("AH0 B AH1 V",   "vowel"),   # starts with vowel
    ("S T AA1 R T",   "hard"),    # S
    ("M AY1 N D",     "soft"),    # M
])
def test_first_syllable_attack(arpabet, expected):
    assert first_syllable_attack(arpabet) == expected


def test_consonant_density_pure_hard():
    # "stark": S T AA1 R K → 5 phonemes, 3 hard (S, T, K), 1 soft (R), 1 vowel
    # density = hard / total = 3 / 5 = 0.6
    assert consonant_density("S T AA1 R K") == pytest.approx(0.6)


def test_consonant_density_pure_soft():
    # "moon": M UW1 N → 3 phonemes, 0 hard, 2 soft, 1 vowel
    assert consonant_density("M UW1 N") == pytest.approx(0.0)


def test_consonant_density_no_consonants():
    # "I": AY1 → 1 phoneme, 0 consonants
    assert consonant_density("AY1") == pytest.approx(0.0)
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_derived.py -v
```

Expected: NEW failures.

- [ ] **Step 3: Implement**

Append to: `songwriter/src/songwriter/seeds/derived.py`

```python
from songwriter.seeds.phonemes import attack_class, is_hard_consonant


def first_syllable_attack(arpabet: str) -> str:
    """Classify the first phoneme of the word as hard | soft | vowel."""
    tokens = _tokens(arpabet)
    if not tokens:
        return ""
    return attack_class(strip_stress(tokens[0]))


def consonant_density(arpabet: str) -> float:
    """Ratio of hard consonants to total phonemes."""
    tokens = _tokens(arpabet)
    if not tokens:
        return 0.0
    hard = sum(1 for t in tokens if is_hard_consonant(strip_stress(t)))
    return hard / len(tokens)
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
pytest tests/test_derived.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/derived.py tests/test_derived.py
git commit -m "feat(data): derive first-syllable attack + consonant density"
```

---

## Task 9: CMUdict download + parse

**Files:**
- Create: `songwriter/src/songwriter/seeds/cmudict.py`
- Create: `songwriter/tests/test_cmudict.py`
- Create: `songwriter/tests/fixtures/cmudict_sample.txt` (small fixture)

CMUdict is at https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict — public domain, ~4MB. We download once into `data/cache/cmudict.dict`, then parse on subsequent runs without re-fetching.

- [ ] **Step 1: Create the test fixture**

File: `songwriter/tests/fixtures/cmudict_sample.txt`

```
;;; comment line, must be skipped
LOVE  L AH1 V
HEART  HH AA1 R T
ABOVE  AH0 B AH1 V
LOVE(2)  L UH1 V
START  S T AA1 R T
```

(Note the `(2)` suffix — CMUdict marks alternate pronunciations this way; we keep only the primary.)

- [ ] **Step 2: Write the failing test**

File: `songwriter/tests/test_cmudict.py`

```python
from pathlib import Path

import pytest

from songwriter.seeds import cmudict


FIXTURE = Path(__file__).parent / "fixtures" / "cmudict_sample.txt"


def test_parse_skips_comments_and_alternates():
    entries = cmudict.parse_file(FIXTURE)
    assert entries["love"] == "L AH1 V"
    assert entries["heart"] == "HH AA1 R T"
    assert entries["above"] == "AH0 B AH1 V"
    assert entries["start"] == "S T AA1 R T"
    # alternate pronunciation discarded
    assert entries["love"] != "L UH1 V"


def test_parse_lowercases_words():
    entries = cmudict.parse_file(FIXTURE)
    for k in entries:
        assert k == k.lower()


def test_download_caches(tmp_path, monkeypatch):
    target = tmp_path / "cmudict.dict"

    call_count = {"n": 0}
    def fake_get(url, timeout=None):
        call_count["n"] += 1
        class FakeResp:
            status_code = 200
            text = "LOVE  L AH1 V\n"
            def raise_for_status(self): pass
        return FakeResp()

    monkeypatch.setattr(cmudict.requests, "get", fake_get)
    cmudict.download(target)
    cmudict.download(target)  # should hit cache
    assert call_count["n"] == 1
    assert target.exists()
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_cmudict.py -v
```

Expected: all FAIL.

- [ ] **Step 4: Implement `cmudict.py`**

File: `songwriter/src/songwriter/seeds/cmudict.py`

```python
"""Download + parse CMUdict.

Source: https://github.com/cmusphinx/cmudict (public domain)
"""

import re
from pathlib import Path

import requests

CMUDICT_URL = (
    "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict"
)

_ALT_SUFFIX = re.compile(r"\(\d+\)$")


def download(path: Path) -> None:
    """Download CMUdict to `path` if not already present."""
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(CMUDICT_URL, timeout=60)
    resp.raise_for_status()
    path.write_text(resp.text)


def parse_file(path: Path) -> dict[str, str]:
    """Parse CMUdict file → {lowercase_word: arpabet_string}.
    Drops comments, drops alternate-pronunciation entries (KEEP only primary)."""
    entries: dict[str, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(";;;"):
            continue
        # CMUdict format: WORD<spaces>PHONEMES   or  WORD #comment
        # Some lines have "#" comments; strip after first '#'
        if "#" in line:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        word, arpabet = parts
        word = word.lower()
        if _ALT_SUFFIX.search(word):
            continue  # skip alternate pronunciations
        if word in entries:
            continue
        entries[word] = arpabet.strip()
    return entries
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_cmudict.py -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/songwriter/seeds/cmudict.py tests/test_cmudict.py tests/fixtures/cmudict_sample.txt
git commit -m "feat(data): download + parse CMUdict"
```

---

## Task 10: gruut fallback for non-CMUdict words

**Files:**
- Create: `songwriter/src/songwriter/seeds/gruut_fallback.py`
- Create: `songwriter/tests/test_gruut_fallback.py`

CMUdict misses slang, proper nouns, recent words. gruut gives us IPA for those. We do not derive ARPAbet from gruut — gruut-only words get IPA but `arpabet=NULL`. Phase 1 only uses gruut for English; multilingual is Phase 2.

- [ ] **Step 1: Write the failing test**

File: `songwriter/tests/test_gruut_fallback.py`

```python
import pytest

from songwriter.seeds.gruut_fallback import ipa_for_word


def test_ipa_for_known_word():
    # "shadow" — straightforward English, gruut should produce IPA
    ipa = ipa_for_word("shadow", "en")
    assert ipa, "expected non-empty IPA"
    # ʃ is the SH onset; presence is a basic sanity check
    assert "ʃ" in ipa


def test_ipa_for_word_handles_empty():
    assert ipa_for_word("", "en") == ""


def test_ipa_for_unknown_returns_empty_or_best_guess():
    # gruut may g2p a nonsense token; we just require it does not raise
    out = ipa_for_word("zxqvb", "en")
    assert isinstance(out, str)
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_gruut_fallback.py -v
```

Expected: import error / module missing.

- [ ] **Step 3: Implement `gruut_fallback.py`**

File: `songwriter/src/songwriter/seeds/gruut_fallback.py`

```python
"""IPA via gruut for words missing from CMUdict.

We strip gruut's stress marks (ˈ, ˌ) and word/sentence boundaries from the
output to produce a flat IPA string compatible with our `words.ipa` column.
"""

from __future__ import annotations

try:
    from gruut import sentences as _gruut_sentences
except Exception:  # pragma: no cover
    _gruut_sentences = None


_STRIP = {"ˈ", "ˌ", " ", "‖", "|"}


def ipa_for_word(word: str, language: str = "en") -> str:
    if not word or _gruut_sentences is None:
        return ""
    chunks: list[str] = []
    try:
        for sentence in _gruut_sentences(word, lang=language):
            for w in sentence:
                if w.phonemes:
                    chunks.extend(w.phonemes)
    except Exception:
        return ""
    return "".join(c for c in "".join(chunks) if c not in _STRIP)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_gruut_fallback.py -v
```

Expected: 3 PASS. (If gruut's `en` model is not installed, the first test will fail — install it: `pip install "gruut[en]"`.)

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/gruut_fallback.py tests/test_gruut_fallback.py
git commit -m "feat(data): add gruut fallback for non-CMUdict words"
```

---

## Task 11: Words seeder — populate `words` table from CMUdict

**Files:**
- Create: `songwriter/src/songwriter/seeds/seeders/words.py`
- Create: `songwriter/tests/test_seeder_words.py`

This task wires CMUdict → derivations → DB inserts. We bulk-insert in a single transaction for performance (~135K rows should complete in seconds).

- [ ] **Step 1: Write the failing test**

File: `songwriter/tests/test_seeder_words.py`

```python
from pathlib import Path

import sqlite3
import pytest

from songwriter.seeds import db as db_module
from songwriter.seeds.seeders import words as words_seeder


FIXTURE = Path(__file__).parent / "fixtures" / "cmudict_sample.txt"


def test_seed_words_inserts_rows_with_derivations(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)

    inserted = words_seeder.seed_from_cmudict(target, FIXTURE)
    assert inserted >= 4  # love, heart, above, start

    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM words WHERE word = 'love' AND language = 'en'"
    ).fetchone()
    assert row is not None
    assert row["arpabet"] == "L AH1 V"
    assert row["ipa"] == "lʌv"
    assert row["syllables"] == 1
    assert row["stress_pattern"] == "1"
    assert row["rhyme_class"] == "AH-V"
    assert row["vowel_shape"] == "short-U"
    assert row["first_syllable_attack"] == "soft"
    assert row["consonant_density"] == pytest.approx(0.0)  # L is soft
    assert row["syllable_count_class"] == "mono"


def test_seed_words_is_idempotent(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    n1 = words_seeder.seed_from_cmudict(target, FIXTURE)
    n2 = words_seeder.seed_from_cmudict(target, FIXTURE)
    conn = db_module.connect(target)
    count = conn.execute("SELECT COUNT(*) AS c FROM words").fetchone()["c"]
    assert count == n1
    assert n2 == 0  # nothing new on second run
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_seeder_words.py -v
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the words seeder**

File: `songwriter/src/songwriter/seeds/seeders/words.py`

```python
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds import cmudict
from songwriter.seeds.arpabet_ipa import arpabet_to_ipa
from songwriter.seeds.derived import (
    syllable_count,
    syllable_count_class,
    stress_pattern,
    rhyme_class,
    vowel_shape,
    first_syllable_attack,
    consonant_density,
)


def seed_from_cmudict(db_path: Path, cmudict_path: Path) -> int:
    """Insert CMUdict words into `words` table. Returns number of new rows."""
    entries = cmudict.parse_file(cmudict_path)
    conn = db_module.connect(db_path)
    inserted = 0
    try:
        existing = {
            row["word"]
            for row in conn.execute(
                "SELECT word FROM words WHERE language = 'en'"
            )
        }
        rows = []
        for word, arpabet in entries.items():
            if word in existing:
                continue
            try:
                ipa = arpabet_to_ipa(arpabet)
                syl = syllable_count(arpabet)
                rows.append((
                    word, "en", ipa, arpabet,
                    syl, stress_pattern(arpabet), rhyme_class(arpabet),
                    vowel_shape(arpabet), first_syllable_attack(arpabet),
                    consonant_density(arpabet), syllable_count_class(syl),
                ))
            except (ValueError, IndexError):
                continue
        if rows:
            conn.executemany(
                """
                INSERT INTO words
                  (word, language, ipa, arpabet, syllables, stress_pattern,
                   rhyme_class, vowel_shape, first_syllable_attack,
                   consonant_density, syllable_count_class)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )
            inserted = len(rows)
        conn.commit()
    finally:
        conn.close()
    return inserted
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_seeder_words.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/seeders/words.py tests/test_seeder_words.py
git commit -m "feat(data): seed words table from CMUdict with derivations"
```

---

## Task 12: YAML loader infrastructure

**Files:**
- Create: `songwriter/src/songwriter/seeds/yaml_loader.py`
- Create: `songwriter/tests/test_yaml_loader.py`

A thin layer over pyyaml that (a) loads files, (b) validates required top-level keys, (c) provides a `load_all_in` helper for directory-based loaders (vocab/ and songwriters/).

- [ ] **Step 1: Write the failing test**

File: `songwriter/tests/test_yaml_loader.py`

```python
import pytest

from songwriter.seeds.yaml_loader import load_yaml, load_all_in, require_keys


def test_load_yaml_returns_dict(tmp_path):
    p = tmp_path / "x.yml"
    p.write_text("name: foo\nvalue: 42\n")
    assert load_yaml(p) == {"name": "foo", "value": 42}


def test_load_all_in_finds_yml_and_yaml(tmp_path):
    (tmp_path / "a.yml").write_text("name: a\n")
    (tmp_path / "b.yaml").write_text("name: b\n")
    (tmp_path / "ignore.txt").write_text("name: c\n")
    items = load_all_in(tmp_path)
    names = sorted(d["name"] for d in items)
    assert names == ["a", "b"]


def test_load_all_in_recurses(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.yml").write_text("name: a\n")
    (tmp_path / "b.yml").write_text("name: b\n")
    items = load_all_in(tmp_path)
    assert len(items) == 2


def test_require_keys_passes_when_all_present():
    require_keys({"a": 1, "b": 2}, ["a", "b"], context="test")


def test_require_keys_raises_with_helpful_message():
    with pytest.raises(ValueError) as exc:
        require_keys({"a": 1}, ["a", "b"], context="myfile.yml")
    assert "myfile.yml" in str(exc.value)
    assert "b" in str(exc.value)
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_yaml_loader.py -v
```

Expected: import error.

- [ ] **Step 3: Implement `yaml_loader.py`**

File: `songwriter/src/songwriter/seeds/yaml_loader.py`

```python
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict:
    with path.open() as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected top-level mapping, got {type(data).__name__}")
    return data


def load_all_in(directory: Path) -> list[dict]:
    """Recursively load all .yml/.yaml files in directory, return list of dicts."""
    out = []
    for ext in ("*.yml", "*.yaml"):
        for p in sorted(directory.rglob(ext)):
            out.append(load_yaml(p))
    return out


def require_keys(data: dict, keys: list[str], *, context: str) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise ValueError(f"{context}: missing required keys: {missing}")
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_yaml_loader.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/songwriter/seeds/yaml_loader.py tests/test_yaml_loader.py
git commit -m "feat(data): add YAML loader infrastructure"
```

---

## Task 13: Genres + sub-genres seed

**Files:**
- Create: `songwriter/data/genres.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/genres.py`
- Create: `songwriter/tests/test_seeder_genres.py`

12 top-level genres per spec. Pop and R&B get fully expanded sub-genre trees in Phase 1; the other 10 ship with their parent rows + a couple of representative sub-genres so cross-genre lookups don't crash. Phase 2 fleshes out the rest.

- [ ] **Step 1: Write `data/genres.yml`**

File: `songwriter/data/genres.yml`

```yaml
genres:
  - slug: pop
    name: Pop
    typical_bpm_min: 90
    typical_bpm_max: 130
    description: "Mainstream pop and adjacent commercial styles."
    sub_genres:
      - slug: dance-pop
        name: Dance-Pop
        typical_bpm_min: 110
        typical_bpm_max: 128
      - slug: synth-pop
        name: Synth-Pop
        typical_bpm_min: 100
        typical_bpm_max: 124
      - slug: indie-pop
        name: Indie Pop
        typical_bpm_min: 92
        typical_bpm_max: 120
      - slug: hyperpop
        name: Hyperpop
        typical_bpm_min: 140
        typical_bpm_max: 170
      - slug: alt-pop
        name: Alt-Pop
        typical_bpm_min: 88
        typical_bpm_max: 116
      - slug: country-pop
        name: Country-Pop
        typical_bpm_min: 90
        typical_bpm_max: 118

  - slug: rnb
    name: R&B
    typical_bpm_min: 60
    typical_bpm_max: 105
    description: "R&B, neo-soul, and contemporary alt-R&B."
    sub_genres:
      - slug: contemporary-rnb
        name: Contemporary R&B
        typical_bpm_min: 70
        typical_bpm_max: 100
      - slug: alt-rnb
        name: Alternative R&B
        typical_bpm_min: 60
        typical_bpm_max: 95
      - slug: neo-soul
        name: Neo-Soul
        typical_bpm_min: 70
        typical_bpm_max: 95
      - slug: 90s-rnb
        name: 90s R&B
        typical_bpm_min: 70
        typical_bpm_max: 100
      - slug: pbrnb
        name: PBR&B
        typical_bpm_min: 60
        typical_bpm_max: 90

  - slug: rap
    name: Rap / Hip-Hop
    typical_bpm_min: 60
    typical_bpm_max: 160
    sub_genres:
      - { slug: trap, name: Trap, typical_bpm_min: 130, typical_bpm_max: 160 }
      - { slug: boom-bap, name: Boom-Bap, typical_bpm_min: 85, typical_bpm_max: 100 }

  - slug: rock
    name: Rock
    typical_bpm_min: 90
    typical_bpm_max: 160
    sub_genres:
      - { slug: alt-rock, name: Alt-Rock, typical_bpm_min: 100, typical_bpm_max: 140 }
      - { slug: indie-rock, name: Indie Rock, typical_bpm_min: 95, typical_bpm_max: 135 }

  - slug: metal
    name: Metal / Heavy
    typical_bpm_min: 100
    typical_bpm_max: 220
    sub_genres:
      - { slug: deathcore, name: Deathcore, typical_bpm_min: 130, typical_bpm_max: 200 }

  - slug: country
    name: Country
    typical_bpm_min: 80
    typical_bpm_max: 130
    sub_genres:
      - { slug: pop-country, name: Pop Country, typical_bpm_min: 95, typical_bpm_max: 125 }

  - slug: edm
    name: Electronic / EDM
    typical_bpm_min: 100
    typical_bpm_max: 160
    sub_genres:
      - { slug: house, name: House, typical_bpm_min: 118, typical_bpm_max: 128 }

  - slug: latin
    name: Latin
    typical_bpm_min: 80
    typical_bpm_max: 130
    sub_genres:
      - { slug: reggaeton, name: Reggaeton, typical_bpm_min: 90, typical_bpm_max: 100 }

  - slug: folk
    name: Folk / Singer-Songwriter
    typical_bpm_min: 60
    typical_bpm_max: 110
    sub_genres:
      - { slug: contemporary-folk, name: Contemporary Folk, typical_bpm_min: 70, typical_bpm_max: 110 }

  - slug: soul
    name: Soul / Funk / Disco / Gospel
    typical_bpm_min: 70
    typical_bpm_max: 130
    sub_genres:
      - { slug: classic-soul, name: Classic Soul, typical_bpm_min: 80, typical_bpm_max: 110 }

  - slug: afrobeats
    name: Afrobeats
    typical_bpm_min: 100
    typical_bpm_max: 120
    sub_genres:
      - { slug: alte, name: Alté, typical_bpm_min: 95, typical_bpm_max: 115 }

  - slug: grime
    name: UK Grime
    typical_bpm_min: 130
    typical_bpm_max: 145
    sub_genres:
      - { slug: classic-grime, name: Classic Grime, typical_bpm_min: 138, typical_bpm_max: 142 }
```

- [ ] **Step 2: Write the failing test**

File: `songwriter/tests/test_seeder_genres.py`

```python
from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import genres as genres_seeder


def test_seed_genres_loads_pop_and_rnb(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    conn = db_module.connect(target)

    pop = conn.execute("SELECT * FROM genres WHERE slug = 'pop'").fetchone()
    assert pop is not None
    assert pop["typical_bpm_min"] == 90

    pop_subs = conn.execute(
        "SELECT slug FROM sub_genres WHERE genre_id = ?", (pop["id"],)
    ).fetchall()
    slugs = {r["slug"] for r in pop_subs}
    assert {"dance-pop", "synth-pop", "indie-pop", "hyperpop", "alt-pop", "country-pop"} <= slugs


def test_seed_genres_has_all_12_top_level(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM genres").fetchone()["c"]
    assert n == 12


def test_seed_genres_is_idempotent(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM genres").fetchone()["c"]
    assert n == 12
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_seeder_genres.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement seeder**

File: `songwriter/src/songwriter/seeds/seeders/genres.py`

```python
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["genres"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for g in data["genres"]:
            require_keys(g, ["slug", "name"], context=f"{yaml_path}#{g.get('slug')}")
            conn.execute(
                """
                INSERT INTO genres (slug, name, description,
                                    typical_bpm_min, typical_bpm_max, notes_for_suno)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    typical_bpm_min = excluded.typical_bpm_min,
                    typical_bpm_max = excluded.typical_bpm_max,
                    notes_for_suno = excluded.notes_for_suno
                """,
                (
                    g["slug"], g["name"], g.get("description"),
                    g.get("typical_bpm_min"), g.get("typical_bpm_max"),
                    g.get("notes_for_suno"),
                ),
            )
            genre_id = conn.execute(
                "SELECT id FROM genres WHERE slug = ?", (g["slug"],)
            ).fetchone()["id"]
            for sg in g.get("sub_genres", []):
                require_keys(sg, ["slug", "name"], context=f"{yaml_path}#{g['slug']}/{sg.get('slug')}")
                conn.execute(
                    """
                    INSERT INTO sub_genres (genre_id, slug, name, description,
                                            typical_bpm_min, typical_bpm_max, notes_for_suno)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(genre_id, slug) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        typical_bpm_min = excluded.typical_bpm_min,
                        typical_bpm_max = excluded.typical_bpm_max,
                        notes_for_suno = excluded.notes_for_suno
                    """,
                    (
                        genre_id, sg["slug"], sg["name"], sg.get("description"),
                        sg.get("typical_bpm_min"), sg.get("typical_bpm_max"),
                        sg.get("notes_for_suno"),
                    ),
                )
        conn.commit()
    finally:
        conn.close()
```

Note: this requires the schema to declare `UNIQUE(slug)` on `genres` (already in place from Task 2) and `UNIQUE(genre_id, slug)` on `sub_genres` (already in place).

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_seeder_genres.py -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add data/genres.yml src/songwriter/seeds/seeders/genres.py tests/test_seeder_genres.py
git commit -m "feat(data): seed 12 genres + sub-genre tree (Pop+R&B fully expanded)"
```

---

## Task 14: Cadence patterns seed

**Files:**
- Create: `songwriter/data/cadence_patterns.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/cadence_patterns.py`
- Create: `songwriter/tests/test_seeder_cadence.py`

10 patterns from the user's existing cadence pattern library (see `cadence_pattern_library.txt` in the repo's source documents). Stress templates use `1`/`0` strings; `?` marks variable positions.

- [ ] **Step 1: Write `data/cadence_patterns.yml`**

File: `songwriter/data/cadence_patterns.yml`

```yaml
patterns:
  - slug: straight-4-beat
    name: Straight 4-Beat
    syllable_template: "8"
    stress_template: "10101010"
    typical_genres: [pop, rock, country]
    example_lines:
      - "I been waiting on the phone all night"
    rhyme_compatibility:
      end: [perfect, near]
      internal: low

  - slug: double-time-rap
    name: Double-Time Rap
    syllable_template: "16"
    stress_template: "1010101010101010"
    typical_genres: [rap]
    example_lines:
      - "Pull up to the spot like a heat-seek missile in the city tonight"
    rhyme_compatibility:
      end: [perfect, near, slant]
      internal: high

  - slug: triplet
    name: Triplet
    syllable_template: "12"
    stress_template: "100100100100"
    typical_genres: [rap]
    example_lines:
      - "Money in the bag and the pistol on the floor again"
    rhyme_compatibility:
      end: [perfect, near]
      internal: medium

  - slug: grime-swing
    name: Grime Swing
    syllable_template: "10-12"
    stress_template: "1?1?1?1?"
    typical_genres: [grime]
    example_lines:
      - "Linkin uptown when the night gets dark"
    rhyme_compatibility:
      end: [near, slant]
      internal: high

  - slug: melodic-glide
    name: Melodic Glide
    syllable_template: "6-9"
    stress_template: "10010"
    typical_genres: [rnb, pop]
    example_lines:
      - "You called me late, said you couldn't sleep"
    rhyme_compatibility:
      end: [perfect, near, slant]
      internal: low

  - slug: punchline
    name: Punchline
    syllable_template: "4-7"
    stress_template: "11"
    typical_genres: [rap, pop]
    example_lines:
      - "Hit different now"
    rhyme_compatibility:
      end: [perfect]
      internal: low

  - slug: breakdown-chant
    name: Breakdown Chant
    syllable_template: "3-5"
    stress_template: "1"
    typical_genres: [metal, rock]
    example_lines:
      - "Bury me deep"
    rhyme_compatibility:
      end: [perfect, near]
      internal: low

  - slug: pop-hook
    name: Pop Hook
    syllable_template: "6-10"
    stress_template: "10101"
    typical_genres: [pop]
    example_lines:
      - "I don't wanna lose you tonight"
    rhyme_compatibility:
      end: [perfect, near]
      internal: medium

  - slug: storytelling
    name: Storytelling
    syllable_template: "10-14"
    stress_template: "0101010101"
    typical_genres: [folk, country, rap]
    example_lines:
      - "She came around the bend and the rain was falling"
    rhyme_compatibility:
      end: [perfect, near, slant]
      internal: medium

  - slug: hybrid
    name: Hybrid
    syllable_template: "?"
    stress_template: "?"
    typical_genres: [pop, rnb, rap]
    example_lines:
      - "Free-form section that swaps cadence mid-line"
    rhyme_compatibility:
      end: [perfect, near, slant, vowel]
      internal: high
```

- [ ] **Step 2: Write the failing test**

File: `songwriter/tests/test_seeder_cadence.py`

```python
import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import cadence_patterns as cadence_seeder


def test_seed_cadence_loads_10(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    cadence_seeder.seed(target, DATA_DIR / "cadence_patterns.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM cadence_patterns").fetchone()["c"]
    assert n == 10


def test_seed_cadence_known_slugs(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    cadence_seeder.seed(target, DATA_DIR / "cadence_patterns.yml")
    conn = db_module.connect(target)
    slugs = {r["slug"] for r in conn.execute("SELECT slug FROM cadence_patterns")}
    expected = {
        "straight-4-beat", "double-time-rap", "triplet", "grime-swing",
        "melodic-glide", "punchline", "breakdown-chant", "pop-hook",
        "storytelling", "hybrid",
    }
    assert expected == slugs


def test_seed_cadence_json_columns_parse(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    cadence_seeder.seed(target, DATA_DIR / "cadence_patterns.yml")
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM cadence_patterns WHERE slug = 'melodic-glide'"
    ).fetchone()
    genres = json.loads(row["typical_genres"])
    assert "rnb" in genres
    rhyme = json.loads(row["rhyme_compatibility"])
    assert "perfect" in rhyme["end"]
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_seeder_cadence.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement seeder**

File: `songwriter/src/songwriter/seeds/seeders/cadence_patterns.py`

```python
import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["patterns"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for p in data["patterns"]:
            require_keys(p, ["slug", "name"], context=f"{yaml_path}#{p.get('slug')}")
            conn.execute(
                """
                INSERT INTO cadence_patterns
                  (slug, name, syllable_template, stress_template,
                   typical_genres, example_lines, rhyme_compatibility)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    syllable_template = excluded.syllable_template,
                    stress_template = excluded.stress_template,
                    typical_genres = excluded.typical_genres,
                    example_lines = excluded.example_lines,
                    rhyme_compatibility = excluded.rhyme_compatibility
                """,
                (
                    p["slug"], p["name"],
                    p.get("syllable_template"), p.get("stress_template"),
                    json.dumps(p.get("typical_genres") or []),
                    json.dumps(p.get("example_lines") or []),
                    json.dumps(p.get("rhyme_compatibility") or {}),
                ),
            )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_seeder_cadence.py -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add data/cadence_patterns.yml src/songwriter/seeds/seeders/cadence_patterns.py tests/test_seeder_cadence.py
git commit -m "feat(data): seed 10 cadence patterns from existing library"
```

---

## Task 15: Structure templates seed

**Files:**
- Create: `songwriter/data/structure_templates.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/structure_templates.py`
- Create: `songwriter/tests/test_seeder_structure.py`

Templates ship: pop standard, pop dance, rnb intimate-confession, rnb late-night-drift. Phase 2 expands.

- [ ] **Step 1: Write `data/structure_templates.yml`**

File: `songwriter/data/structure_templates.yml`

```yaml
templates:
  - slug: pop.standard
    name: Pop Standard
    genre_compatibility: [pop, dance-pop, synth-pop, alt-pop, country-pop, indie-pop]
    sections:
      - { section: intro,    energy: 0.35, syllable_target: 0  }
      - { section: verse,    energy: 0.45, syllable_target: 64 }
      - { section: pre,      energy: 0.65, syllable_target: 32 }
      - { section: chorus,   energy: 0.85, syllable_target: 48 }
      - { section: verse,    energy: 0.5,  syllable_target: 64 }
      - { section: pre,      energy: 0.7,  syllable_target: 32 }
      - { section: chorus,   energy: 0.9,  syllable_target: 48 }
      - { section: bridge,   energy: 0.55, syllable_target: 32 }
      - { section: chorus,   energy: 1.0,  syllable_target: 48 }

  - slug: pop.dance
    name: Pop Dance
    genre_compatibility: [pop, dance-pop, hyperpop]
    sections:
      - { section: intro,    energy: 0.4,  syllable_target: 0  }
      - { section: verse,    energy: 0.55, syllable_target: 56 }
      - { section: chorus,   energy: 0.85, syllable_target: 48 }
      - { section: drop,     energy: 1.0,  syllable_target: 16 }
      - { section: verse,    energy: 0.6,  syllable_target: 56 }
      - { section: chorus,   energy: 0.9,  syllable_target: 48 }
      - { section: drop,     energy: 1.0,  syllable_target: 16 }
      - { section: outro,    energy: 0.5,  syllable_target: 16 }

  - slug: rnb.intimate-confession
    name: R&B Intimate Confession
    genre_compatibility: [rnb, contemporary-rnb, alt-rnb, neo-soul, pbrnb]
    sections:
      - { section: intro,    energy: 0.3,  syllable_target: 0  }
      - { section: verse,    energy: 0.4,  syllable_target: 72 }
      - { section: pre,      energy: 0.55, syllable_target: 24 }
      - { section: chorus,   energy: 0.7,  syllable_target: 48 }
      - { section: verse,    energy: 0.45, syllable_target: 72 }
      - { section: chorus,   energy: 0.75, syllable_target: 48 }
      - { section: bridge,   energy: 0.85, syllable_target: 40 }
      - { section: chorus,   energy: 0.7,  syllable_target: 48 }

  - slug: rnb.late-night-drift
    name: R&B Late-Night Drift
    genre_compatibility: [rnb, alt-rnb, pbrnb]
    sections:
      - { section: intro,    energy: 0.25, syllable_target: 0  }
      - { section: verse,    energy: 0.35, syllable_target: 64 }
      - { section: chorus,   energy: 0.55, syllable_target: 36 }
      - { section: verse,    energy: 0.4,  syllable_target: 64 }
      - { section: chorus,   energy: 0.6,  syllable_target: 36 }
      - { section: outro,    energy: 0.4,  syllable_target: 16 }
```

- [ ] **Step 2: Write the failing test**

File: `songwriter/tests/test_seeder_structure.py`

```python
import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import structure_templates as struct_seeder


def test_seed_structure_loads_4_templates(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    struct_seeder.seed(target, DATA_DIR / "structure_templates.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM structure_templates").fetchone()["c"]
    assert n == 4


def test_seed_structure_pop_standard(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    struct_seeder.seed(target, DATA_DIR / "structure_templates.yml")
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM structure_templates WHERE slug = 'pop.standard'"
    ).fetchone()
    sections = json.loads(row["sections"])
    assert sections[0]["section"] == "intro"
    chorus_sections = [s for s in sections if s["section"] == "chorus"]
    assert len(chorus_sections) == 3
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_seeder_structure.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement seeder**

File: `songwriter/src/songwriter/seeds/seeders/structure_templates.py`

```python
import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["templates"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for t in data["templates"]:
            require_keys(t, ["slug", "name", "sections"], context=f"{yaml_path}#{t.get('slug')}")
            conn.execute(
                """
                INSERT INTO structure_templates
                  (slug, name, sections, genre_compatibility)
                VALUES (?,?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    sections = excluded.sections,
                    genre_compatibility = excluded.genre_compatibility
                """,
                (
                    t["slug"], t["name"],
                    json.dumps(t["sections"]),
                    json.dumps(t.get("genre_compatibility") or []),
                ),
            )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_seeder_structure.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add data/structure_templates.yml src/songwriter/seeds/seeders/structure_templates.py tests/test_seeder_structure.py
git commit -m "feat(data): seed structure templates (pop + rnb)"
```

---

## Task 16: Production fingerprints seed

**Files:**
- Create: `songwriter/data/production_fingerprints.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/production_fingerprints.py`
- Create: `songwriter/tests/test_seeder_production.py`

One fingerprint per Phase 1 sub-genre (Pop's 6 + R&B's 5 = 11). The `negative_descriptors` list directly fuels Suno anti-prompts and is critical for the "intent-output mismatch" failure.

- [ ] **Step 1: Write `data/production_fingerprints.yml`**

File: `songwriter/data/production_fingerprints.yml`

```yaml
fingerprints:
  - sub_genre: pop.dance-pop
    instrumentation:
      drums: ["four-on-the-floor kick", "tight snare", "hat on offbeat"]
      bass: ["pulsing synth bass", "sidechain to kick"]
      keys: ["bright pluck synth", "stab chord pads"]
    vocal_style:
      delivery: ["confident", "hook-forward", "double-tracked chorus"]
      effects: ["subtle plate reverb", "short slapback delay"]
    mix_attributes:
      brightness: high
      compression: heavy
      width: wide
    positive_descriptors:
      - "polished radio mix"
      - "punchy four-on-the-floor"
      - "bright synth pluck lead"
    negative_descriptors:
      - "lo-fi"
      - "woody acoustic guitar"
      - "tape saturation"
      - "muddy low end"

  - sub_genre: pop.synth-pop
    instrumentation:
      drums: ["gated reverb snare", "linn-style kick"]
      bass: ["analog mono synth bass"]
      keys: ["warm analog pads", "arpeggiated lead"]
    vocal_style:
      delivery: ["airy", "doubled octave", "breathy verses"]
      effects: ["chorus", "long plate reverb"]
    mix_attributes: { brightness: medium-high, compression: moderate, width: wide }
    positive_descriptors:
      - "analog-warm synth bass"
      - "gated reverb on snare"
      - "lush pad bed"
    negative_descriptors:
      - "trap hi-hats"
      - "808 sub-bass"
      - "metal guitars"

  - sub_genre: pop.indie-pop
    instrumentation:
      drums: ["live kit", "tambourine"]
      bass: ["clean fingered electric bass"]
      keys: ["upright piano", "vibes"]
      guitars: ["clean Strat", "12-string acoustic"]
    vocal_style: { delivery: ["intimate", "single-tracked verses"], effects: ["room reverb", "subtle compression"] }
    mix_attributes: { brightness: medium, compression: light, width: medium }
    positive_descriptors: ["warm room ambience", "live drum kit", "twangy clean guitar"]
    negative_descriptors: ["club drop", "EDM bass", "autotuned hook"]

  - sub_genre: pop.hyperpop
    instrumentation:
      drums: ["hyper-fast snare rolls", "distorted kick"]
      bass: ["square sub-bass", "wobble"]
      keys: ["bright supersaw", "candy plucks"]
    vocal_style: { delivery: ["pitch-shifted", "chipmunked", "autotune-as-instrument"], effects: ["heavy autotune", "telephone EQ"] }
    mix_attributes: { brightness: extreme, compression: brick-walled, width: extreme }
    positive_descriptors: ["pitched-up vocals", "supersaw lead", "glitchy edits"]
    negative_descriptors: ["organic instruments", "live drums", "natural reverb"]

  - sub_genre: pop.alt-pop
    instrumentation:
      drums: ["minimal kit", "808 layered with live snare"]
      bass: ["mono sub", "muted electric"]
      keys: ["dusty Rhodes", "atmospheric pads"]
    vocal_style: { delivery: ["close-mic'd", "whisper-to-belt dynamic"], effects: ["close-mic compression", "tape saturation"] }
    mix_attributes: { brightness: medium, compression: moderate, width: medium }
    positive_descriptors: ["close-mic vocal", "muted electric texture", "tape warmth"]
    negative_descriptors: ["four-on-the-floor", "EDM drop", "stadium reverb"]

  - sub_genre: pop.country-pop
    instrumentation:
      drums: ["live kit with brushes optional", "tambourine"]
      bass: ["clean P-bass"]
      guitars: ["acoustic strum", "dobro/steel slide", "telecaster lead"]
    vocal_style: { delivery: ["clear", "story-forward", "twang light"], effects: ["light slap delay", "natural plate"] }
    mix_attributes: { brightness: medium, compression: moderate, width: medium-wide }
    positive_descriptors: ["acoustic guitar foundation", "telecaster twang", "natural drum kit"]
    negative_descriptors: ["heavy autotune", "trap hi-hats", "EDM synth lead"]

  - sub_genre: rnb.contemporary-rnb
    instrumentation:
      drums: ["tight programmed", "snappy snare", "808 layered with kick"]
      bass: ["deep 808 sub"]
      keys: ["Rhodes", "soft pads"]
    vocal_style: { delivery: ["smooth", "melismatic", "stacked harmonies"], effects: ["plate reverb", "doubled chorus"] }
    mix_attributes: { brightness: medium, compression: moderate, width: medium }
    positive_descriptors: ["Rhodes electric piano", "stacked vocal harmonies", "warm sub-bass"]
    negative_descriptors: ["distorted guitars", "punk drums", "EDM drop"]

  - sub_genre: rnb.alt-rnb
    instrumentation:
      drums: ["sparse programmed", "off-grid percussion"]
      bass: ["muted sub", "occasional bass slide"]
      keys: ["dusty Rhodes", "ambient pads", "field-recording textures"]
    vocal_style: { delivery: ["intimate", "breathy", "whispered ad-libs"], effects: ["close-mic", "spring reverb", "tape hiss"] }
    mix_attributes: { brightness: low-medium, compression: light, width: medium }
    positive_descriptors: ["dusty Rhodes", "muted sub-bass", "intimate close-mic vocal"]
    negative_descriptors: ["bright pop snare", "stadium reverb", "EDM build-up"]

  - sub_genre: rnb.neo-soul
    instrumentation:
      drums: ["live kit with pocket groove", "ghost notes"]
      bass: ["fingered electric bass with slides"]
      keys: ["Wurli", "Rhodes", "Hammond B3"]
    vocal_style: { delivery: ["warm", "melismatic", "improvisational ad-libs"], effects: ["analog plate", "subtle tape compression"] }
    mix_attributes: { brightness: medium, compression: moderate, width: medium }
    positive_descriptors: ["live drum pocket", "Wurlitzer electric piano", "fingered bass with slides"]
    negative_descriptors: ["trap hi-hats", "autotuned vocals", "EDM elements"]

  - sub_genre: rnb.90s-rnb
    instrumentation:
      drums: ["MPC swing", "snare on 2 and 4"]
      bass: ["deep round bass synth"]
      keys: ["Rhodes layered with strings"]
    vocal_style: { delivery: ["powerhouse runs", "group harmonies"], effects: ["lush reverb", "doubled lead"] }
    mix_attributes: { brightness: medium-high, compression: moderate, width: wide }
    positive_descriptors: ["MPC swing groove", "lush string pads", "powerhouse vocal runs"]
    negative_descriptors: ["lo-fi production", "minimalism", "indie-pop snare"]

  - sub_genre: rnb.pbrnb
    instrumentation:
      drums: ["spacey programmed", "reverb-drenched claps"]
      bass: ["filtered sub"]
      keys: ["dreamy pads", "filtered Rhodes"]
    vocal_style: { delivery: ["echoey", "layered", "reverb-soaked"], effects: ["heavy plate", "long delay throws"] }
    mix_attributes: { brightness: low-medium, compression: moderate, width: very wide }
    positive_descriptors: ["reverb-drenched claps", "filtered sub-bass", "dreamy pad bed"]
    negative_descriptors: ["dry mix", "live drums", "country instrumentation"]
```

- [ ] **Step 2: Write the failing test**

File: `songwriter/tests/test_seeder_production.py`

```python
import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import (
    genres as genres_seeder,
    production_fingerprints as prod_seeder,
)


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    prod_seeder.seed(target, DATA_DIR / "production_fingerprints.yml")
    return target


def test_seed_production_fingerprints_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM production_fingerprints").fetchone()["c"]
    assert n == 11  # 6 pop sub-genres + 5 rnb sub-genres


def test_seed_production_alt_rnb_negatives(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        """
        SELECT pf.* FROM production_fingerprints pf
        JOIN sub_genres sg ON sg.id = pf.sub_genre_id
        WHERE sg.slug = 'alt-rnb'
        """
    ).fetchone()
    negs = json.loads(row["negative_descriptors"])
    assert any("bright" in n.lower() for n in negs)
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_seeder_production.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement seeder**

File: `songwriter/src/songwriter/seeds/seeders/production_fingerprints.py`

```python
import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def _resolve_sub_genre_id(conn, dotted: str) -> int:
    """Accept either 'genre.subgenre' or just 'subgenre' (must be unique)."""
    if "." in dotted:
        genre_slug, sub_slug = dotted.split(".", 1)
        row = conn.execute(
            """
            SELECT sg.id FROM sub_genres sg
            JOIN genres g ON g.id = sg.genre_id
            WHERE g.slug = ? AND sg.slug = ?
            """,
            (genre_slug, sub_slug),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM sub_genres WHERE slug = ?", (dotted,)
        ).fetchone()
    if not row:
        raise ValueError(f"unknown sub-genre: {dotted!r}")
    return row["id"]


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["fingerprints"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for fp in data["fingerprints"]:
            require_keys(fp, ["sub_genre"], context=f"{yaml_path}#{fp.get('sub_genre')}")
            sg_id = _resolve_sub_genre_id(conn, fp["sub_genre"])
            conn.execute(
                """
                INSERT INTO production_fingerprints
                  (sub_genre_id, instrumentation, vocal_style, mix_attributes,
                   positive_descriptors, negative_descriptors)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(sub_genre_id) DO UPDATE SET
                    instrumentation = excluded.instrumentation,
                    vocal_style = excluded.vocal_style,
                    mix_attributes = excluded.mix_attributes,
                    positive_descriptors = excluded.positive_descriptors,
                    negative_descriptors = excluded.negative_descriptors
                """,
                (
                    sg_id,
                    json.dumps(fp.get("instrumentation") or {}),
                    json.dumps(fp.get("vocal_style") or {}),
                    json.dumps(fp.get("mix_attributes") or {}),
                    json.dumps(fp.get("positive_descriptors") or []),
                    json.dumps(fp.get("negative_descriptors") or []),
                ),
            )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_seeder_production.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add data/production_fingerprints.yml src/songwriter/seeds/seeders/production_fingerprints.py tests/test_seeder_production.py
git commit -m "feat(data): seed production fingerprints for pop + rnb sub-genres"
```

---

## Task 17: Emotion-tempo map seed

**Files:**
- Create: `songwriter/data/emotion_tempo_map.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/emotion_tempo_map.py`
- Create: `songwriter/tests/test_seeder_emotion_tempo.py`

This is the table that fixes the "love-ballad → upbeat pop" failure mode. We seed combinations across the 6 emotion-arcs the wizard offers (escalation / collapse / redemption / surrender / defiance / nostalgia) × Phase 1 sub-genres.

- [ ] **Step 1: Write `data/emotion_tempo_map.yml`**

File: `songwriter/data/emotion_tempo_map.yml`

```yaml
entries:
  # POP — DANCE-POP
  - { emotion: escalation,  sub_genre: pop.dance-pop, bpm_min: 116, bpm_max: 126, energy_curve: [0.4,0.55,0.75,0.9,1.0],         anti_prompts: [ballad, melancholic, sparse] }
  - { emotion: defiance,    sub_genre: pop.dance-pop, bpm_min: 118, bpm_max: 128, energy_curve: [0.5,0.7,0.85,1.0,1.0],          anti_prompts: [ballad, intimate, whisper] }
  - { emotion: surrender,   sub_genre: pop.dance-pop, bpm_min: 100, bpm_max: 110, energy_curve: [0.4,0.55,0.7,0.85,0.7],         anti_prompts: [aggressive, EDM-drop] }

  # POP — SYNTH-POP
  - { emotion: nostalgia,   sub_genre: pop.synth-pop, bpm_min: 100, bpm_max: 116, energy_curve: [0.35,0.5,0.7,0.65,0.8],          anti_prompts: [trap, autotune-heavy] }
  - { emotion: redemption,  sub_genre: pop.synth-pop, bpm_min: 104, bpm_max: 118, energy_curve: [0.4,0.55,0.7,0.85,1.0],          anti_prompts: [collapse-mood, lo-fi] }

  # POP — INDIE-POP
  - { emotion: collapse,    sub_genre: pop.indie-pop, bpm_min: 88,  bpm_max: 104, energy_curve: [0.45,0.55,0.4,0.6,0.45],         anti_prompts: [club, EDM-drop, four-on-the-floor] }
  - { emotion: nostalgia,   sub_genre: pop.indie-pop, bpm_min: 92,  bpm_max: 108, energy_curve: [0.4,0.55,0.65,0.6,0.7],          anti_prompts: [trap, autotune-heavy] }

  # POP — HYPERPOP
  - { emotion: defiance,    sub_genre: pop.hyperpop,  bpm_min: 150, bpm_max: 168, energy_curve: [0.7,0.9,1.0,1.0,1.0],            anti_prompts: [ballad, organic-instruments] }

  # POP — ALT-POP
  - { emotion: collapse,    sub_genre: pop.alt-pop,   bpm_min: 86,  bpm_max: 102, energy_curve: [0.35,0.45,0.4,0.55,0.5],         anti_prompts: [club, four-on-the-floor] }
  - { emotion: surrender,   sub_genre: pop.alt-pop,   bpm_min: 80,  bpm_max: 96,  energy_curve: [0.3,0.45,0.55,0.5,0.65],         anti_prompts: [club, EDM-build] }

  # POP — COUNTRY-POP
  - { emotion: redemption,  sub_genre: pop.country-pop, bpm_min: 96,  bpm_max: 116, energy_curve: [0.4,0.55,0.7,0.8,0.95],        anti_prompts: [trap, EDM-drop, autotune-heavy] }
  - { emotion: nostalgia,   sub_genre: pop.country-pop, bpm_min: 90,  bpm_max: 106, energy_curve: [0.4,0.5,0.6,0.65,0.75],        anti_prompts: [trap, EDM-drop] }

  # R&B — CONTEMPORARY
  - { emotion: surrender,   sub_genre: rnb.contemporary-rnb, bpm_min: 72, bpm_max: 88, energy_curve: [0.35,0.45,0.6,0.75,0.65],   anti_prompts: [aggressive, EDM-drop, four-on-the-floor] }
  - { emotion: escalation,  sub_genre: rnb.contemporary-rnb, bpm_min: 84, bpm_max: 100, energy_curve: [0.4,0.55,0.7,0.85,0.95],   anti_prompts: [punk-drums, distorted-guitar] }

  # R&B — ALT-RNB
  - { emotion: surrender,   sub_genre: rnb.alt-rnb,   bpm_min: 64,  bpm_max: 78,  energy_curve: [0.25,0.4,0.55,0.7,0.55],         anti_prompts: [bright-pop-snare, stadium-reverb, EDM-build] }
  - { emotion: collapse,    sub_genre: rnb.alt-rnb,   bpm_min: 60,  bpm_max: 76,  energy_curve: [0.3,0.4,0.35,0.5,0.45],          anti_prompts: [club, EDM-build, autotune-heavy] }
  - { emotion: nostalgia,   sub_genre: rnb.alt-rnb,   bpm_min: 68,  bpm_max: 82,  energy_curve: [0.3,0.45,0.55,0.6,0.5],          anti_prompts: [bright, club] }

  # R&B — NEO-SOUL
  - { emotion: redemption,  sub_genre: rnb.neo-soul,  bpm_min: 76,  bpm_max: 92,  energy_curve: [0.4,0.55,0.7,0.8,0.95],          anti_prompts: [trap, autotune-heavy, EDM] }
  - { emotion: nostalgia,   sub_genre: rnb.neo-soul,  bpm_min: 72,  bpm_max: 86,  energy_curve: [0.35,0.5,0.6,0.7,0.65],          anti_prompts: [trap, club] }

  # R&B — 90s
  - { emotion: escalation,  sub_genre: rnb.90s-rnb,   bpm_min: 84,  bpm_max: 100, energy_curve: [0.4,0.55,0.7,0.85,0.95],         anti_prompts: [lo-fi, indie-snare, minimal] }
  - { emotion: defiance,    sub_genre: rnb.90s-rnb,   bpm_min: 88,  bpm_max: 102, energy_curve: [0.5,0.65,0.8,0.95,1.0],          anti_prompts: [lo-fi, minimal] }

  # R&B — PBRNB
  - { emotion: collapse,    sub_genre: rnb.pbrnb,     bpm_min: 60,  bpm_max: 76,  energy_curve: [0.3,0.4,0.35,0.5,0.45],          anti_prompts: [dry-mix, live-drums, country-instrumentation] }
  - { emotion: surrender,   sub_genre: rnb.pbrnb,     bpm_min: 64,  bpm_max: 80,  energy_curve: [0.3,0.45,0.6,0.7,0.55],          anti_prompts: [bright, four-on-the-floor] }
```

- [ ] **Step 2: Write the failing test**

File: `songwriter/tests/test_seeder_emotion_tempo.py`

```python
import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import (
    genres as genres_seeder,
    emotion_tempo_map as et_seeder,
)


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    et_seeder.seed(target, DATA_DIR / "emotion_tempo_map.yml")
    return target


def test_seed_emotion_tempo_alt_rnb_surrender(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        """
        SELECT et.* FROM emotion_tempo_map et
        JOIN sub_genres sg ON sg.id = et.sub_genre_id
        WHERE et.emotion = 'surrender' AND sg.slug = 'alt-rnb'
        """
    ).fetchone()
    assert row is not None
    assert row["bpm_min"] == 64
    assert row["bpm_max"] == 78
    anti = json.loads(row["anti_prompts"])
    assert "EDM-build" in anti


def test_seed_emotion_tempo_minimum_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM emotion_tempo_map").fetchone()["c"]
    assert n >= 20
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_seeder_emotion_tempo.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement seeder**

File: `songwriter/src/songwriter/seeds/seeders/emotion_tempo_map.py`

```python
import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys
from songwriter.seeds.seeders.production_fingerprints import _resolve_sub_genre_id


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["entries"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for e in data["entries"]:
            require_keys(
                e, ["emotion", "sub_genre", "bpm_min", "bpm_max"],
                context=f"{yaml_path}#{e.get('emotion')}/{e.get('sub_genre')}",
            )
            sg_id = _resolve_sub_genre_id(conn, e["sub_genre"])
            conn.execute(
                """
                INSERT INTO emotion_tempo_map
                  (emotion, sub_genre_id, bpm_min, bpm_max, energy_curve, anti_prompts)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(emotion, sub_genre_id) DO UPDATE SET
                    bpm_min = excluded.bpm_min,
                    bpm_max = excluded.bpm_max,
                    energy_curve = excluded.energy_curve,
                    anti_prompts = excluded.anti_prompts
                """,
                (
                    e["emotion"], sg_id, e["bpm_min"], e["bpm_max"],
                    json.dumps(e.get("energy_curve") or []),
                    json.dumps(e.get("anti_prompts") or []),
                ),
            )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_seeder_emotion_tempo.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add data/emotion_tempo_map.yml src/songwriter/seeds/seeders/emotion_tempo_map.py tests/test_seeder_emotion_tempo.py
git commit -m "feat(data): seed emotion-tempo map for pop + rnb"
```

---

## Task 18: Suno burn list seed

**Files:**
- Create: `songwriter/data/burn_list.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/burn_list.py`
- Create: `songwriter/tests/test_seeder_burn_list.py`

The token-bias burn list. Spec says ~50 entries. Words come from the user's last30days research session and observed Suno drift. Each has severity + drift direction + alternatives.

- [ ] **Step 1: Write `data/burn_list.yml`**

File: `songwriter/data/burn_list.yml`

```yaml
words:
  # CORE 5 — confirmed from spec
  - { word: neon,    severity: extreme, drift_direction: synthwave-cinematic, alternatives: [argon, halogen, lit, glowing, fluorescent] }
  - { word: echo,    severity: extreme, drift_direction: ambient-cliche,      alternatives: [ringing, resound, lingering, repeat, return] }
  - { word: ghost,   severity: extreme, drift_direction: indie-cliche,        alternatives: [trace, residue, shadow-of, afterimage, leftover] }
  - { word: silver,  severity: strong,  drift_direction: synthwave,           alternatives: [chrome, steel, mercury, metal, quiet-light] }
  - { word: shadow,  severity: strong,  drift_direction: moody-cinematic,     alternatives: [dim, dusk, half-light, silhouette, shade] }

  # SYNTHWAVE / 80s DRIFT
  - { word: chrome,    severity: strong,  drift_direction: synthwave,        alternatives: [polished, mirror, slick] }
  - { word: midnight,  severity: strong,  drift_direction: moody-cliche,     alternatives: [late, 2am, after-hours, dead-of-night] }
  - { word: city-lights, severity: mild,  drift_direction: 80s-cinema,       alternatives: [downtown, traffic-glow, the-strip] }
  - { word: highway,   severity: mild,    drift_direction: synthwave,        alternatives: [the-405, the-turnpike, county-line] }
  - { word: skyline,   severity: mild,    drift_direction: cinematic,        alternatives: [the-blocks, rooftops, the-grid] }
  - { word: horizon,   severity: mild,    drift_direction: cinematic,        alternatives: [the-edge, where-the-sky-tips] }

  # MOODY / DRAMATIC DRIFT
  - { word: whisper,   severity: strong,  drift_direction: moody-cliche,     alternatives: [murmur, breath-out, mouth-close] }
  - { word: scream,    severity: strong,  drift_direction: melodrama,        alternatives: [yelled, throat-raw, shouted] }
  - { word: bleed,     severity: strong,  drift_direction: melodrama,        alternatives: [drip, run-thin, leak] }
  - { word: broken,    severity: extreme, drift_direction: generic-emo,      alternatives: [splintered, hollowed, snapped, wrecked] }
  - { word: shattered, severity: strong,  drift_direction: melodrama,        alternatives: [splintered, in-pieces, ground-down] }
  - { word: fragile,   severity: strong,  drift_direction: indie-cliche,     alternatives: [thin-skinned, paperweight, ready-to-go] }
  - { word: empty,     severity: strong,  drift_direction: generic-emo,      alternatives: [hollow, scoured, gut-out] }
  - { word: hollow,    severity: mild,    drift_direction: generic-emo,      alternatives: [scooped, gutted, vacant-room] }
  - { word: numb,      severity: strong,  drift_direction: generic-emo,      alternatives: [muffled, asleep, dead-feet] }
  - { word: lost,      severity: strong,  drift_direction: generic,          alternatives: [adrift, off-the-map, wrong-side] }
  - { word: alone,     severity: strong,  drift_direction: generic,          alternatives: [one-of-one, just-me, room-to-myself] }

  # FIRE / SMOKE CLICHES
  - { word: fire,      severity: strong,  drift_direction: cliche,           alternatives: [match-strike, smoke-curl, lit-up] }
  - { word: flame,     severity: mild,    drift_direction: cliche,           alternatives: [match, ember, lit-tip] }
  - { word: burning,   severity: strong,  drift_direction: cliche,           alternatives: [smouldering, going-up, crackling] }
  - { word: smoke,     severity: mild,    drift_direction: cliche,           alternatives: [haze, exhale, blue-cloud] }
  - { word: ashes,     severity: mild,    drift_direction: cliche,           alternatives: [grey-dust, soot, char] }

  # WEATHER / CINEMATIC DRIFT
  - { word: storm,     severity: strong,  drift_direction: cinematic,        alternatives: [low-pressure, the-front-coming, sky-down] }
  - { word: rain,      severity: mild,    drift_direction: cliche,           alternatives: [downpour, the-drip, sky-leaking] }
  - { word: thunder,   severity: strong,  drift_direction: cinematic,        alternatives: [the-rolling, the-crack-overhead] }
  - { word: lightning, severity: strong,  drift_direction: cinematic,        alternatives: [strike, white-flash, fork-in-the-sky] }
  - { word: ocean,     severity: mild,    drift_direction: cinematic,        alternatives: [the-water, salt, deep-end] }
  - { word: stars,     severity: mild,    drift_direction: cliche,           alternatives: [pinpricks, the-sky-up-there, satellites] }

  # ACTION-MOVIE DRIFT
  - { word: warrior,   severity: extreme, drift_direction: anthem-cliche,    alternatives: [fighter, holdout, last-one-up] }
  - { word: soldier,   severity: extreme, drift_direction: anthem-cliche,    alternatives: [marching, on-deck, frontline] }
  - { word: battle,    severity: strong,  drift_direction: anthem-cliche,    alternatives: [the-fight, going-rounds, knockdown] }
  - { word: rise,      severity: strong,  drift_direction: anthem-cliche,    alternatives: [stand-up, get-back, on-my-feet] }
  - { word: fall,      severity: mild,    drift_direction: anthem-cliche,    alternatives: [drop, came-down, knees-out] }

  # GENERIC EMOTION VERBS
  - { word: feel,      severity: strong,  drift_direction: generic-emotion,  alternatives: [taste, register, catch, run-cold] }
  - { word: heart,     severity: strong,  drift_direction: generic-emotion,  alternatives: [chest, ribs, heart-rate, the-thump] }
  - { word: soul,      severity: strong,  drift_direction: generic-emotion,  alternatives: [the-shape-of-me, what's-left] }
  - { word: tears,     severity: strong,  drift_direction: generic-emotion,  alternatives: [eyes-wet, cheek-stripe, salt-down] }
  - { word: cry,       severity: mild,    drift_direction: generic-emotion,  alternatives: [break-down, wet-up, lose-it] }

  # AI-COMMON FILLER
  - { word: forever,   severity: strong,  drift_direction: pop-cliche,       alternatives: [the-long-haul, til-they-shut-it-down] }
  - { word: always,    severity: mild,    drift_direction: pop-cliche,       alternatives: [every-time, no-matter-when] }
  - { word: never,     severity: mild,    drift_direction: pop-cliche,       alternatives: [not-once, zero-times, dead-stop] }
  - { word: dreams,    severity: strong,  drift_direction: pop-cliche,       alternatives: [REM, what-I-see-asleep, the-running-loop] }
  - { word: angel,     severity: strong,  drift_direction: pop-cliche,       alternatives: [saint, the-soft-one] }
  - { word: heaven,    severity: strong,  drift_direction: pop-cliche,       alternatives: [the-up-there, no-floor] }
  - { word: paradise,  severity: strong,  drift_direction: pop-cliche,       alternatives: [the-clean-place, no-rules-zone] }
  - { word: pain,      severity: extreme, drift_direction: generic-emotion,  alternatives: [the-ache, soreness, the-bruise] }
  - { word: love,      severity: mild,    drift_direction: generic-emotion,  alternatives: [the-thing-we-have, what-we-call-it] }
```

- [ ] **Step 2: Write the failing test**

File: `songwriter/tests/test_seeder_burn_list.py`

```python
import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import burn_list as burn_seeder


def test_seed_burn_list_minimum_count(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    burn_seeder.seed(target, DATA_DIR / "burn_list.yml")
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM suno_burn_list").fetchone()["c"]
    assert n >= 50


def test_seed_burn_list_neon_extreme(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    burn_seeder.seed(target, DATA_DIR / "burn_list.yml")
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM suno_burn_list WHERE word = 'neon'"
    ).fetchone()
    assert row["severity"] == "extreme"
    alts = json.loads(row["alternatives"])
    assert "argon" in alts
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_seeder_burn_list.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement seeder**

File: `songwriter/src/songwriter/seeds/seeders/burn_list.py`

```python
import json
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["words"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for w in data["words"]:
            require_keys(w, ["word", "severity"], context=f"{yaml_path}#{w.get('word')}")
            conn.execute(
                """
                INSERT INTO suno_burn_list (word, severity, drift_direction, alternatives)
                VALUES (?,?,?,?)
                ON CONFLICT(word) DO UPDATE SET
                    severity = excluded.severity,
                    drift_direction = excluded.drift_direction,
                    alternatives = excluded.alternatives
                """,
                (
                    w["word"].lower(), w["severity"],
                    w.get("drift_direction"),
                    json.dumps(w.get("alternatives") or []),
                ),
            )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_seeder_burn_list.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add data/burn_list.yml src/songwriter/seeds/seeders/burn_list.py tests/test_seeder_burn_list.py
git commit -m "feat(data): seed Suno token-bias burn list (~50 entries)"
```

---

## Task 19: Vocab banks seed — Pop (6 banks)

**Files:**
- Create: `songwriter/data/vocab/pop/confession.yml`
- Create: `songwriter/data/vocab/pop/infatuation.yml`
- Create: `songwriter/data/vocab/pop/breakup.yml`
- Create: `songwriter/data/vocab/pop/party.yml`
- Create: `songwriter/data/vocab/pop/nostalgia.yml`
- Create: `songwriter/data/vocab/pop/empowerment.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/vocab_banks.py`
- Create: `songwriter/tests/test_seeder_vocab.py`
- Create: `songwriter/tests/fixtures/cmudict_vocab_words.txt`

The vocab seeder resolves each word against the `words` table. Words missing from CMUdict get inserted via gruut fallback. This is where the phonetic master index meets curated emotional tagging.

Each bank file declares one bank; it does NOT have to enumerate every English word — just the curated word set the lyric-writing layer queries first.

- [ ] **Step 1: Write `data/vocab/pop/confession.yml`**

File: `songwriter/data/vocab/pop/confession.yml`

```yaml
slug: pop.confession
name: Pop / Confession
description: Self-disclosure vocabulary for confessional pop verses.
words:
  - { word: said,        emotional_weight: 0.5, imagery_class: physical }
  - { word: kept,        emotional_weight: 0.7, imagery_class: physical }
  - { word: saved,       emotional_weight: 0.7, imagery_class: physical }
  - { word: typed,       emotional_weight: 0.5, imagery_class: physical }
  - { word: deleted,     emotional_weight: 0.6, imagery_class: physical }
  - { word: opened,      emotional_weight: 0.6, imagery_class: physical }
  - { word: window,      emotional_weight: 0.4, imagery_class: sensory }
  - { word: hallway,     emotional_weight: 0.5, imagery_class: sensory }
  - { word: kitchen,     emotional_weight: 0.6, imagery_class: sensory }
  - { word: sweater,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: voicemail,   emotional_weight: 0.8, imagery_class: physical }
  - { word: receipt,     emotional_weight: 0.7, imagery_class: physical }
  - { word: gas,         emotional_weight: 0.4, imagery_class: physical }
  - { word: address,     emotional_weight: 0.5, imagery_class: physical }
  - { word: bathroom,    emotional_weight: 0.5, imagery_class: sensory }
  - { word: counted,     emotional_weight: 0.5, imagery_class: physical }
  - { word: practiced,   emotional_weight: 0.6, imagery_class: physical }
  - { word: rehearsed,   emotional_weight: 0.6, imagery_class: physical }
  - { word: meant,       emotional_weight: 0.7, imagery_class: abstract }
```

- [ ] **Step 2: Write `data/vocab/pop/infatuation.yml`**

File: `songwriter/data/vocab/pop/infatuation.yml`

```yaml
slug: pop.infatuation
name: Pop / Infatuation
description: Early-stage attraction and butterflies-in-the-stomach vocabulary.
words:
  - { word: caught,      emotional_weight: 0.7, imagery_class: physical }
  - { word: spinning,    emotional_weight: 0.7, imagery_class: physical }
  - { word: dizzy,       emotional_weight: 0.7, imagery_class: physical }
  - { word: blushing,    emotional_weight: 0.7, imagery_class: physical }
  - { word: tripping,    emotional_weight: 0.6, imagery_class: physical }
  - { word: laughing,    emotional_weight: 0.6, imagery_class: physical }
  - { word: humming,     emotional_weight: 0.6, imagery_class: physical }
  - { word: glowing,     emotional_weight: 0.6, imagery_class: sensory }
  - { word: floating,    emotional_weight: 0.7, imagery_class: physical }
  - { word: butterflies, emotional_weight: 0.8, imagery_class: metaphorical }
  - { word: fluttering,  emotional_weight: 0.7, imagery_class: physical }
  - { word: smiling,     emotional_weight: 0.6, imagery_class: physical }
  - { word: hooked,      emotional_weight: 0.8, imagery_class: metaphorical }
  - { word: swooning,    emotional_weight: 0.7, imagery_class: physical, cliche_flag: true }
  - { word: melting,     emotional_weight: 0.7, imagery_class: physical }
```

- [ ] **Step 3: Write `data/vocab/pop/breakup.yml`**

File: `songwriter/data/vocab/pop/breakup.yml`

```yaml
slug: pop.breakup
name: Pop / Breakup
description: Aftermath-of-a-relationship vocabulary, weighted toward concrete imagery over generic emo.
words:
  - { word: keys,        emotional_weight: 0.8, imagery_class: physical }
  - { word: drawer,      emotional_weight: 0.7, imagery_class: physical }
  - { word: jacket,      emotional_weight: 0.8, imagery_class: physical }
  - { word: toothbrush,  emotional_weight: 0.9, imagery_class: physical }
  - { word: photos,      emotional_weight: 0.7, imagery_class: physical }
  - { word: empty,       emotional_weight: 0.7, imagery_class: abstract, ai_bias_flag: true }
  - { word: silent,      emotional_weight: 0.6, imagery_class: sensory }
  - { word: half,        emotional_weight: 0.7, imagery_class: physical }
  - { word: closet,      emotional_weight: 0.7, imagery_class: physical }
  - { word: returned,    emotional_weight: 0.7, imagery_class: physical }
  - { word: blocked,     emotional_weight: 0.7, imagery_class: physical }
  - { word: deleted,     emotional_weight: 0.7, imagery_class: physical }
  - { word: tagged,      emotional_weight: 0.6, imagery_class: physical }
  - { word: untagged,    emotional_weight: 0.7, imagery_class: physical }
  - { word: silence,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: lighter,     emotional_weight: 0.7, imagery_class: physical }
  - { word: matchbook,   emotional_weight: 0.7, imagery_class: physical }
  - { word: tomorrow,    emotional_weight: 0.5, imagery_class: abstract }
```

- [ ] **Step 4: Write `data/vocab/pop/party.yml`**

File: `songwriter/data/vocab/pop/party.yml`

```yaml
slug: pop.party
name: Pop / Party
description: Big-night vocabulary, leaning into specific concrete texture rather than generic "tonight we own it".
words:
  - { word: balcony,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: speakers,    emotional_weight: 0.7, imagery_class: sensory }
  - { word: confetti,    emotional_weight: 0.7, imagery_class: sensory }
  - { word: bottles,     emotional_weight: 0.7, imagery_class: physical }
  - { word: heels,       emotional_weight: 0.7, imagery_class: physical }
  - { word: jacket,      emotional_weight: 0.6, imagery_class: physical }
  - { word: rooftop,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: elevator,    emotional_weight: 0.6, imagery_class: physical }
  - { word: smoke,       emotional_weight: 0.5, imagery_class: sensory, ai_bias_flag: true }
  - { word: dancing,     emotional_weight: 0.7, imagery_class: physical }
  - { word: shouting,    emotional_weight: 0.6, imagery_class: physical }
  - { word: laughing,    emotional_weight: 0.6, imagery_class: physical }
  - { word: spinning,    emotional_weight: 0.6, imagery_class: physical }
  - { word: tipping,     emotional_weight: 0.6, imagery_class: physical }
  - { word: drink,       emotional_weight: 0.5, imagery_class: physical }
  - { word: tonight,     emotional_weight: 0.5, imagery_class: abstract, cliche_flag: true }
```

- [ ] **Step 5: Write `data/vocab/pop/nostalgia.yml`**

File: `songwriter/data/vocab/pop/nostalgia.yml`

```yaml
slug: pop.nostalgia
name: Pop / Nostalgia
description: Looking-backward vocabulary, anchored in specific objects/places rather than "remember when".
words:
  - { word: polaroid,    emotional_weight: 0.8, imagery_class: physical }
  - { word: cassette,    emotional_weight: 0.8, imagery_class: physical }
  - { word: bedroom,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: backseat,    emotional_weight: 0.7, imagery_class: physical }
  - { word: cigarette,   emotional_weight: 0.7, imagery_class: physical }
  - { word: parking,     emotional_weight: 0.6, imagery_class: physical }
  - { word: pavement,    emotional_weight: 0.6, imagery_class: sensory }
  - { word: porch,       emotional_weight: 0.7, imagery_class: sensory }
  - { word: window,      emotional_weight: 0.6, imagery_class: sensory }
  - { word: summer,      emotional_weight: 0.6, imagery_class: sensory }
  - { word: cracked,     emotional_weight: 0.7, imagery_class: physical }
  - { word: taped,       emotional_weight: 0.7, imagery_class: physical }
  - { word: faded,       emotional_weight: 0.6, imagery_class: sensory }
  - { word: handwritten, emotional_weight: 0.7, imagery_class: physical }
  - { word: kitchen,     emotional_weight: 0.6, imagery_class: sensory }
  - { word: jukebox,     emotional_weight: 0.7, imagery_class: physical }
```

- [ ] **Step 6: Write `data/vocab/pop/empowerment.yml`**

File: `songwriter/data/vocab/pop/empowerment.yml`

```yaml
slug: pop.empowerment
name: Pop / Empowerment
description: Self-reclamation vocabulary, weighted toward specific actions rather than "rise up".
words:
  - { word: deleted,     emotional_weight: 0.7, imagery_class: physical }
  - { word: blocked,     emotional_weight: 0.7, imagery_class: physical }
  - { word: signed,      emotional_weight: 0.6, imagery_class: physical }
  - { word: bought,      emotional_weight: 0.6, imagery_class: physical }
  - { word: locked,      emotional_weight: 0.6, imagery_class: physical }
  - { word: walked,      emotional_weight: 0.6, imagery_class: physical }
  - { word: changed,     emotional_weight: 0.5, imagery_class: abstract }
  - { word: stronger,    emotional_weight: 0.7, imagery_class: abstract }
  - { word: louder,      emotional_weight: 0.7, imagery_class: sensory }
  - { word: brighter,    emotional_weight: 0.6, imagery_class: sensory }
  - { word: bolder,      emotional_weight: 0.7, imagery_class: abstract }
  - { word: enough,      emotional_weight: 0.7, imagery_class: abstract }
  - { word: anymore,     emotional_weight: 0.6, imagery_class: abstract }
  - { word: keys,        emotional_weight: 0.7, imagery_class: physical }
  - { word: door,        emotional_weight: 0.6, imagery_class: physical }
  - { word: signature,   emotional_weight: 0.7, imagery_class: physical }
```

- [ ] **Step 7: Write the failing test (with a small CMUdict fixture covering the words used)**

First, build a small CMUdict fixture so tests don't need to download the real one. We'll include only the words referenced above.

File: `songwriter/tests/fixtures/cmudict_vocab_words.txt`

```
;;; minimal CMUdict subset for vocab seeder tests
SAID  S EH1 D
KEPT  K EH1 P T
SAVED  S EY1 V D
TYPED  T AY1 P T
DELETED  D IH0 L IY1 T IH0 D
OPENED  OW1 P AH0 N D
WINDOW  W IH1 N D OW0
HALLWAY  HH AO1 L W EY2
KITCHEN  K IH1 CH AH0 N
SWEATER  S W EH1 T ER0
VOICEMAIL  V OY1 S M EY2 L
RECEIPT  R IH0 S IY1 T
GAS  G AE1 S
ADDRESS  AE1 D R EH2 S
BATHROOM  B AE1 TH R UW2 M
COUNTED  K AW1 N T IH0 D
PRACTICED  P R AE1 K T IH0 S T
REHEARSED  R IH0 HH ER1 S T
MEANT  M EH1 N T
KEYS  K IY1 Z
DRAWER  D R AO1 R
JACKET  JH AE1 K AH0 T
TOOTHBRUSH  T UW1 TH B R AH2 SH
PHOTOS  F OW1 T OW0 Z
EMPTY  EH1 M P T IY0
SILENT  S AY1 L AH0 N T
HALF  HH AE1 F
CLOSET  K L AA1 Z AH0 T
RETURNED  R IH0 T ER1 N D
BLOCKED  B L AA1 K T
TAGGED  T AE1 G D
SILENCE  S AY1 L AH0 N S
LIGHTER  L AY1 T ER0
TOMORROW  T AH0 M AA1 R OW0
CAUGHT  K AO1 T
SPINNING  S P IH1 N IH0 NG
DIZZY  D IH1 Z IY0
TRIPPING  T R IH1 P IH0 NG
LAUGHING  L AE1 F IH0 NG
HUMMING  HH AH1 M IH0 NG
GLOWING  G L OW1 IH0 NG
FLOATING  F L OW1 T IH0 NG
BUTTERFLIES  B AH1 T ER0 F L AY2 Z
SMILING  S M AY1 L IH0 NG
HOOKED  HH UH1 K T
MELTING  M EH1 L T IH0 NG
BALCONY  B AE1 L K AH0 N IY0
SPEAKERS  S P IY1 K ER0 Z
CONFETTI  K AH0 N F EH1 T IY0
BOTTLES  B AA1 T AH0 L Z
HEELS  HH IY1 L Z
ROOFTOP  R UW1 F T AA2 P
ELEVATOR  EH1 L AH0 V EY2 T ER0
SMOKE  S M OW1 K
DANCING  D AE1 N S IH0 NG
SHOUTING  SH AW1 T IH0 NG
TIPPING  T IH1 P IH0 NG
DRINK  D R IH1 NG K
TONIGHT  T AH0 N AY1 T
POLAROID  P OW1 L ER0 OY2 D
CASSETTE  K AH0 S EH1 T
BEDROOM  B EH1 D R UW2 M
BACKSEAT  B AE1 K S IY1 T
CIGARETTE  S IH1 G ER0 EH2 T
PARKING  P AA1 R K IH0 NG
PAVEMENT  P EY1 V M AH0 N T
PORCH  P AO1 R CH
SUMMER  S AH1 M ER0
CRACKED  K R AE1 K T
TAPED  T EY1 P T
FADED  F EY1 D AH0 D
HANDWRITTEN  HH AE1 N D R IH2 T AH0 N
JUKEBOX  JH UW1 K B AA2 K S
SIGNED  S AY1 N D
BOUGHT  B AO1 T
LOCKED  L AA1 K T
WALKED  W AO1 K T
CHANGED  CH EY1 N JH D
STRONGER  S T R AO1 NG G ER0
LOUDER  L AW1 D ER0
BRIGHTER  B R AY1 T ER0
BOLDER  B OW1 L D ER0
ENOUGH  IH0 N AH1 F
ANYMORE  EH2 N IY0 M AO1 R
DOOR  D AO1 R
SIGNATURE  S IH1 G N AH0 CH ER0
FLUTTERING  F L AH1 T ER0 IH0 NG
SWOONING  S W UW1 N IH0 NG
BLUSHING  B L AH1 SH IH0 NG
MATCHBOOK  M AE1 CH B UH2 K
UNTAGGED  AH0 N T AE1 G D
```

File: `songwriter/tests/test_seeder_vocab.py`

```python
from pathlib import Path

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import (
    words as words_seeder,
    vocab_banks as vocab_seeder,
)


FIXTURE_CMUDICT = Path(__file__).parent / "fixtures" / "cmudict_vocab_words.txt"


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    words_seeder.seed_from_cmudict(target, FIXTURE_CMUDICT)
    return target


def test_seed_vocab_pop_confession(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)

    bank = conn.execute(
        "SELECT * FROM vocab_banks WHERE slug = 'pop.confession'"
    ).fetchone()
    assert bank is not None

    rows = conn.execute(
        """
        SELECT w.word FROM vocab_bank_words vbw
        JOIN words w ON w.id = vbw.word_id
        WHERE vbw.bank_id = ?
        """,
        (bank["id"],),
    ).fetchall()
    words = {r["word"] for r in rows}
    assert "voicemail" in words
    assert "receipt" in words


def test_seed_vocab_pop_six_banks(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)
    pop_banks = conn.execute(
        "SELECT slug FROM vocab_banks WHERE slug LIKE 'pop.%'"
    ).fetchall()
    slugs = {r["slug"] for r in pop_banks}
    assert {"pop.confession", "pop.infatuation", "pop.breakup",
            "pop.party", "pop.nostalgia", "pop.empowerment"} == slugs


def test_seed_vocab_flags_persist(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)
    row = conn.execute(
        """
        SELECT vbw.* FROM vocab_bank_words vbw
        JOIN vocab_banks vb ON vb.id = vbw.bank_id
        JOIN words w ON w.id = vbw.word_id
        WHERE vb.slug = 'pop.party' AND w.word = 'tonight'
        """
    ).fetchone()
    assert row is not None
    assert row["cliche_flag"] == 1
```

- [ ] **Step 8: Run test, verify it fails**

```bash
pytest tests/test_seeder_vocab.py -v
```

Expected: FAIL.

- [ ] **Step 9: Implement the vocab seeder**

File: `songwriter/src/songwriter/seeds/seeders/vocab_banks.py`

```python
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
```

- [ ] **Step 10: Run tests, verify they pass**

```bash
pytest tests/test_seeder_vocab.py -v
```

Expected: 3 PASS.

- [ ] **Step 11: Commit**

```bash
git add data/vocab/pop src/songwriter/seeds/seeders/vocab_banks.py tests/test_seeder_vocab.py tests/fixtures/cmudict_vocab_words.txt
git commit -m "feat(data): seed 6 pop vocab banks (~100 curated words)"
```

---

## Task 20: Vocab banks seed — R&B (6 banks)

**Files:**
- Create: `songwriter/data/vocab/rnb/intimacy.yml`
- Create: `songwriter/data/vocab/rnb/longing.yml`
- Create: `songwriter/data/vocab/rnb/seduction.yml`
- Create: `songwriter/data/vocab/rnb/heartbreak.yml`
- Create: `songwriter/data/vocab/rnb/late-night.yml`
- Create: `songwriter/data/vocab/rnb/devotion.yml`
- Modify: `songwriter/tests/fixtures/cmudict_vocab_words.txt` (add R&B words)
- Modify: `songwriter/tests/test_seeder_vocab.py`

The seeder code already supports any number of bank YAMLs; we only add data + tests here.

- [ ] **Step 1: Write `data/vocab/rnb/intimacy.yml`**

File: `songwriter/data/vocab/rnb/intimacy.yml`

```yaml
slug: rnb.intimacy
name: R&B / Intimacy
description: Quiet-room closeness vocabulary, weighted toward the body and sensory specifics.
words:
  - { word: shoulder,    emotional_weight: 0.7, imagery_class: physical }
  - { word: collarbone,  emotional_weight: 0.8, imagery_class: physical }
  - { word: neck,        emotional_weight: 0.7, imagery_class: physical }
  - { word: pulse,       emotional_weight: 0.7, imagery_class: physical }
  - { word: breath,      emotional_weight: 0.7, imagery_class: physical }
  - { word: eyelash,     emotional_weight: 0.7, imagery_class: physical }
  - { word: forehead,    emotional_weight: 0.6, imagery_class: physical }
  - { word: spine,       emotional_weight: 0.7, imagery_class: physical }
  - { word: knuckles,    emotional_weight: 0.7, imagery_class: physical }
  - { word: thigh,       emotional_weight: 0.7, imagery_class: physical }
  - { word: pillow,      emotional_weight: 0.6, imagery_class: sensory }
  - { word: blanket,     emotional_weight: 0.6, imagery_class: sensory }
  - { word: linen,       emotional_weight: 0.7, imagery_class: sensory }
  - { word: lamplight,   emotional_weight: 0.7, imagery_class: sensory }
  - { word: humming,     emotional_weight: 0.6, imagery_class: sensory }
  - { word: traced,      emotional_weight: 0.7, imagery_class: physical }
  - { word: leaned,      emotional_weight: 0.7, imagery_class: physical }
  - { word: closer,      emotional_weight: 0.6, imagery_class: abstract }
```

- [ ] **Step 2: Write `data/vocab/rnb/longing.yml`**

File: `songwriter/data/vocab/rnb/longing.yml`

```yaml
slug: rnb.longing
name: R&B / Longing
description: Wanting-from-distance vocabulary, weighted toward concrete imagery (typing, scrolling, doorstep) over generic "missing you".
words:
  - { word: typing,      emotional_weight: 0.7, imagery_class: physical }
  - { word: scrolled,    emotional_weight: 0.7, imagery_class: physical }
  - { word: doorstep,    emotional_weight: 0.7, imagery_class: physical }
  - { word: doorway,     emotional_weight: 0.7, imagery_class: physical }
  - { word: passenger,   emotional_weight: 0.7, imagery_class: physical }
  - { word: voicemail,   emotional_weight: 0.8, imagery_class: physical }
  - { word: ceiling,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: streetlight, emotional_weight: 0.6, imagery_class: sensory }
  - { word: pillow,      emotional_weight: 0.6, imagery_class: sensory }
  - { word: drove,       emotional_weight: 0.7, imagery_class: physical }
  - { word: parked,      emotional_weight: 0.7, imagery_class: physical }
  - { word: waited,      emotional_weight: 0.7, imagery_class: physical }
  - { word: counted,     emotional_weight: 0.6, imagery_class: physical }
  - { word: traffic,     emotional_weight: 0.5, imagery_class: sensory }
  - { word: porch,       emotional_weight: 0.7, imagery_class: sensory }
  - { word: rang,        emotional_weight: 0.7, imagery_class: physical }
  - { word: vibration,   emotional_weight: 0.7, imagery_class: sensory }
```

- [ ] **Step 3: Write `data/vocab/rnb/seduction.yml`**

File: `songwriter/data/vocab/rnb/seduction.yml`

```yaml
slug: rnb.seduction
name: R&B / Seduction
description: Slow-pull vocabulary; sensory and physical, avoiding generic erotic shorthand.
words:
  - { word: slowed,      emotional_weight: 0.7, imagery_class: physical }
  - { word: leaned,      emotional_weight: 0.7, imagery_class: physical }
  - { word: lingered,    emotional_weight: 0.7, imagery_class: physical }
  - { word: dimmed,      emotional_weight: 0.7, imagery_class: sensory }
  - { word: traced,      emotional_weight: 0.7, imagery_class: physical }
  - { word: shoulder,    emotional_weight: 0.7, imagery_class: physical }
  - { word: zipper,      emotional_weight: 0.7, imagery_class: physical }
  - { word: collar,      emotional_weight: 0.7, imagery_class: physical }
  - { word: button,      emotional_weight: 0.6, imagery_class: physical }
  - { word: silk,        emotional_weight: 0.7, imagery_class: sensory }
  - { word: cologne,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: perfume,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: lipstick,    emotional_weight: 0.7, imagery_class: physical }
  - { word: candlelight, emotional_weight: 0.6, imagery_class: sensory }
  - { word: doorway,     emotional_weight: 0.6, imagery_class: physical }
  - { word: locked,      emotional_weight: 0.6, imagery_class: physical }
  - { word: closer,      emotional_weight: 0.6, imagery_class: abstract }
```

- [ ] **Step 4: Write `data/vocab/rnb/heartbreak.yml`**

File: `songwriter/data/vocab/rnb/heartbreak.yml`

```yaml
slug: rnb.heartbreak
name: R&B / Heartbreak
description: Aftermath of an R&B relationship; focused on small-room ache rather than melodrama.
words:
  - { word: hoodie,      emotional_weight: 0.7, imagery_class: physical }
  - { word: chargers,    emotional_weight: 0.6, imagery_class: physical }
  - { word: receipts,    emotional_weight: 0.7, imagery_class: physical }
  - { word: rearview,    emotional_weight: 0.7, imagery_class: physical }
  - { word: ringer,      emotional_weight: 0.7, imagery_class: physical }
  - { word: voicemail,   emotional_weight: 0.7, imagery_class: physical }
  - { word: photos,      emotional_weight: 0.6, imagery_class: physical }
  - { word: mattress,    emotional_weight: 0.7, imagery_class: physical }
  - { word: pillows,     emotional_weight: 0.6, imagery_class: physical }
  - { word: kitchen,     emotional_weight: 0.6, imagery_class: sensory }
  - { word: counter,     emotional_weight: 0.6, imagery_class: physical }
  - { word: silent,      emotional_weight: 0.6, imagery_class: sensory }
  - { word: stayed,      emotional_weight: 0.7, imagery_class: physical }
  - { word: left,        emotional_weight: 0.6, imagery_class: physical }
  - { word: muted,       emotional_weight: 0.7, imagery_class: physical }
  - { word: deleted,     emotional_weight: 0.7, imagery_class: physical }
  - { word: archived,    emotional_weight: 0.6, imagery_class: physical }
```

- [ ] **Step 5: Write `data/vocab/rnb/late-night.yml`**

File: `songwriter/data/vocab/rnb/late-night.yml`

```yaml
slug: rnb.late-night
name: R&B / Late Night
description: 2am-after-the-club vocabulary, weighted toward concrete texture rather than "midnight" cliches.
words:
  - { word: rideshare,   emotional_weight: 0.7, imagery_class: physical }
  - { word: backseat,    emotional_weight: 0.7, imagery_class: physical }
  - { word: streetlamp,  emotional_weight: 0.7, imagery_class: sensory }
  - { word: parking,     emotional_weight: 0.6, imagery_class: physical }
  - { word: gas,         emotional_weight: 0.6, imagery_class: physical }
  - { word: pavement,    emotional_weight: 0.6, imagery_class: sensory }
  - { word: lobby,       emotional_weight: 0.6, imagery_class: sensory }
  - { word: hallway,     emotional_weight: 0.6, imagery_class: sensory }
  - { word: elevator,    emotional_weight: 0.6, imagery_class: physical }
  - { word: keycard,     emotional_weight: 0.7, imagery_class: physical }
  - { word: balcony,     emotional_weight: 0.7, imagery_class: sensory }
  - { word: smoking,     emotional_weight: 0.5, imagery_class: physical }
  - { word: barefoot,    emotional_weight: 0.7, imagery_class: physical }
  - { word: silent,      emotional_weight: 0.6, imagery_class: sensory }
```

- [ ] **Step 6: Write `data/vocab/rnb/devotion.yml`**

File: `songwriter/data/vocab/rnb/devotion.yml`

```yaml
slug: rnb.devotion
name: R&B / Devotion
description: Long-haul love vocabulary, focused on day-to-day reliability and specific gestures.
words:
  - { word: kept,        emotional_weight: 0.7, imagery_class: physical }
  - { word: stayed,      emotional_weight: 0.7, imagery_class: physical }
  - { word: showed,      emotional_weight: 0.6, imagery_class: physical }
  - { word: covered,     emotional_weight: 0.7, imagery_class: physical }
  - { word: cooked,      emotional_weight: 0.7, imagery_class: physical }
  - { word: drove,       emotional_weight: 0.6, imagery_class: physical }
  - { word: paid,        emotional_weight: 0.6, imagery_class: physical }
  - { word: held,        emotional_weight: 0.7, imagery_class: physical }
  - { word: prayed,      emotional_weight: 0.7, imagery_class: physical }
  - { word: chose,       emotional_weight: 0.7, imagery_class: physical }
  - { word: keys,        emotional_weight: 0.6, imagery_class: physical }
  - { word: porch,       emotional_weight: 0.6, imagery_class: physical }
  - { word: kitchen,     emotional_weight: 0.6, imagery_class: physical }
  - { word: anniversary, emotional_weight: 0.7, imagery_class: physical }
  - { word: house,       emotional_weight: 0.5, imagery_class: physical }
  - { word: vows,        emotional_weight: 0.7, imagery_class: physical }
```

- [ ] **Step 7: Append R&B words to the test fixture CMUdict**

Append to: `songwriter/tests/fixtures/cmudict_vocab_words.txt`

```
SHOULDER  SH OW1 L D ER0
COLLARBONE  K AA1 L ER0 B OW2 N
NECK  N EH1 K
PULSE  P AH1 L S
BREATH  B R EH1 TH
EYELASH  AY1 L AE2 SH
FOREHEAD  F AO1 R HH EH2 D
SPINE  S P AY1 N
KNUCKLES  N AH1 K AH0 L Z
THIGH  TH AY1
PILLOW  P IH1 L OW0
BLANKET  B L AE1 NG K AH0 T
LINEN  L IH1 N AH0 N
LAMPLIGHT  L AE1 M P L AY2 T
TRACED  T R EY1 S T
LEANED  L IY1 N D
CLOSER  K L OW1 S ER0
TYPING  T AY1 P IH0 NG
SCROLLED  S K R OW1 L D
DOORSTEP  D AO1 R S T EH2 P
DOORWAY  D AO1 R W EY2
PASSENGER  P AE1 S AH0 N JH ER0
CEILING  S IY1 L IH0 NG
STREETLIGHT  S T R IY1 T L AY2 T
DROVE  D R OW1 V
PARKED  P AA1 R K T
WAITED  W EY1 T IH0 D
TRAFFIC  T R AE1 F IH0 K
RANG  R AE1 NG
VIBRATION  V AY0 B R EY1 SH AH0 N
SLOWED  S L OW1 D
LINGERED  L IH1 NG G ER0 D
DIMMED  D IH1 M D
ZIPPER  Z IH1 P ER0
COLLAR  K AA1 L ER0
BUTTON  B AH1 T AH0 N
SILK  S IH1 L K
COLOGNE  K AH0 L OW1 N
PERFUME  P ER0 F Y UW1 M
LIPSTICK  L IH1 P S T IH2 K
CANDLELIGHT  K AE1 N D AH0 L L AY2 T
HOODIE  HH UH1 D IY0
CHARGERS  CH AA1 R JH ER0 Z
RECEIPTS  R IH0 S IY1 T S
REARVIEW  R IH1 R V Y UW2
RINGER  R IH1 NG ER0
MATTRESS  M AE1 T R AH0 S
PILLOWS  P IH1 L OW0 Z
COUNTER  K AW1 N T ER0
STAYED  S T EY1 D
LEFT  L EH1 F T
MUTED  M Y UW1 T IH0 D
ARCHIVED  AA1 R K AY0 V D
RIDESHARE  R AY1 D SH EH2 R
STREETLAMP  S T R IY1 T L AE2 M P
LOBBY  L AA1 B IY0
KEYCARD  K IY1 K AA2 R D
SMOKING  S M OW1 K IH0 NG
BAREFOOT  B EH1 R F UH2 T
KEPT  K EH1 P T
SHOWED  SH OW1 D
COVERED  K AH1 V ER0 D
COOKED  K UH1 K T
PAID  P EY1 D
HELD  HH EH1 L D
PRAYED  P R EY1 D
CHOSE  CH OW1 Z
ANNIVERSARY  AE2 N AH0 V ER1 S ER0 IY0
HOUSE  HH AW1 S
VOWS  V AW1 Z
```

(`kept` is already in the fixture from earlier — it'll be deduplicated by the parser.)

- [ ] **Step 8: Append a test for R&B banks**

Append to: `songwriter/tests/test_seeder_vocab.py`

```python
def test_seed_vocab_rnb_six_banks(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)
    rnb_banks = conn.execute(
        "SELECT slug FROM vocab_banks WHERE slug LIKE 'rnb.%'"
    ).fetchall()
    slugs = {r["slug"] for r in rnb_banks}
    assert {"rnb.intimacy", "rnb.longing", "rnb.seduction",
            "rnb.heartbreak", "rnb.late-night", "rnb.devotion"} == slugs


def test_seed_vocab_rnb_intimacy_collarbone(tmp_path):
    target = _setup(tmp_path)
    vocab_seeder.seed_directory(target, DATA_DIR / "vocab")
    conn = db_module.connect(target)
    rows = conn.execute(
        """
        SELECT w.word FROM vocab_bank_words vbw
        JOIN vocab_banks vb ON vb.id = vbw.bank_id
        JOIN words w ON w.id = vbw.word_id
        WHERE vb.slug = 'rnb.intimacy'
        """
    ).fetchall()
    words = {r["word"] for r in rows}
    assert "collarbone" in words
    assert "shoulder" in words
```

- [ ] **Step 9: Run tests, verify all pass**

```bash
pytest tests/test_seeder_vocab.py -v
```

Expected: 5 PASS (3 prior + 2 new).

- [ ] **Step 10: Commit**

```bash
git add data/vocab/rnb tests/test_seeder_vocab.py tests/fixtures/cmudict_vocab_words.txt
git commit -m "feat(data): seed 6 rnb vocab banks (~100 curated words)"
```

---

## Task 21: Songwriter profiles seed — Pop (5 profiles)

**Files:**
- Create: `songwriter/data/songwriters/pop/diane-warren.yml`
- Create: `songwriter/data/songwriters/pop/max-martin.yml`
- Create: `songwriter/data/songwriters/pop/julia-michaels.yml`
- Create: `songwriter/data/songwriters/pop/finneas.yml`
- Create: `songwriter/data/songwriters/pop/sia.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/songwriter_profiles.py`
- Create: `songwriter/tests/test_seeder_songwriters.py`

Each profile is a craft fingerprint, not a biography. `notable_credits` lists song titles only (no lyrics). `adoption_prompt` is what the skill loads when this lens is active.

- [ ] **Step 1: Write Diane Warren profile (pure-songwriter exemplar)**

File: `songwriter/data/songwriters/pop/diane-warren.yml`

```yaml
slug: diane-warren
display_name: Diane Warren
real_name: Diane Eve Warren
era: 1985-present
primary_genre: pop
role: pure-songwriter
sub_genres: [pop, country-pop, soft-rock]
notable_credits:
  - "Because You Loved Me"
  - "How Do I Live"
  - "Un-Break My Heart"
  - "I Don't Want to Miss a Thing"
  - "If I Could Turn Back Time"
craft_signature:
  - "Big-emotion, plainspoken hooks engineered for a singer's belt range."
  - "Strict end-rhymes; almost never breaks expected scheme — listener trust is the asset."
  - "Verse builds via concrete physical setup, then chorus pivots to declarative emotional summary."
  - "Repeats the title in the chorus 2-3 times, with the strongest delivery on the last repeat."
  - "Uses 'I' and 'you' more than any other pronouns; rarely speaks in 'we'."
personality_traits: [direct, sentimental, romantic, undeflected]
writing_style:
  avg_line_syllables: 9
  rhyme_density: low-to-medium
  internal_rhyme_freq: rare
  end_rhyme_strictness: strict-perfect
  narrative_mode: declarative-confessional
  perspective_default: first-person-to-second-person
  imagery_emphasis: medium
  signature_devices: [title-as-chorus-anchor, builds-on-singer-belt-range]
preferred_cadences: [pop-hook, melodic-glide, storytelling]
vocab_fingerprint:
  signature_words: [heart, love, every-breath, until, forever, anyway, would, never]
  semantic_anchors: [time-passing, sacrifice, the-other-person]
  avoided_words: [neon, chrome, ghost, autotune-ad-libs, slang-heavy]
  vowel_priority_words: [stay, away, day, way, true]   # belt-friendly long vowels
phonetic_fingerprint:
  vowel_preference: long-A, long-O, diphthong
  attack_profile: balanced
  consonant_density: medium
structure_preferences:
  preferred_template: pop.standard
  hook_position: chorus-start
  hook_repeats_per_chorus: 3
hook_style: declarative-title-anchor
reference_tracks:
  - "Because You Loved Me"
  - "I Don't Want to Miss a Thing"
adoption_prompt: |
  Write in the Diane Warren craft mode: plainspoken big-emotion hooks engineered
  for a singer's belt range. Strict end-rhymes; never break the expected scheme.
  Verse should set up a concrete physical situation (a goodbye, a returned object,
  a phone call) and the chorus should pivot to a declarative emotional summary
  built around the song's title. Use 'I' and 'you' freely; avoid 'we'. The line
  in the chorus that lands the title should sit on a long-vowel syllable
  ('stay', 'away', 'true') so a vocalist can sustain it.
```

- [ ] **Step 2: Write Max Martin profile (producer-songwriter, hook architecture)**

File: `songwriter/data/songwriters/pop/max-martin.yml`

```yaml
slug: max-martin
display_name: Max Martin
real_name: Karl Martin Sandberg
era: 1995-present
primary_genre: pop
role: producer-songwriter
sub_genres: [pop, dance-pop, synth-pop]
notable_credits:
  - "...Baby One More Time"
  - "I Want It That Way"
  - "Since U Been Gone"
  - "Roar"
  - "Blank Space"
craft_signature:
  - "'Melodic math' — choruses are constructed so each line's melodic peak lands on a strong accent and a short, percussive consonant."
  - "Pre-choruses tighten cadence and shorten note values to telegraph the chorus drop."
  - "Repetition with one-word substitution between verses ('I' → 'you', 'said' → 'meant') as a structural device."
  - "Short, percussive monosyllables in hooks (it, hit, this, kiss, miss)."
  - "Title is a 2-4 word phrase that scans as the strongest cadence in the chorus."
personality_traits: [precise, rhythmic, structural, ear-first]
writing_style:
  avg_line_syllables: 7
  rhyme_density: medium
  internal_rhyme_freq: medium
  end_rhyme_strictness: strict-perfect
  narrative_mode: hook-summary
  perspective_default: first-or-second-person
  imagery_emphasis: low
  signature_devices: [percussive-hook, parallel-substitution-between-verses, melodic-math]
preferred_cadences: [pop-hook, punchline, straight-4-beat]
vocab_fingerprint:
  signature_words: [it, hit, this, kiss, miss, baby, way, do, did, want]
  semantic_anchors: [direct-address, want, do]
  avoided_words: [philosophical, abstract, multi-syllabic, complex-metaphor]
  vowel_priority_words: [it, hit, this, kiss, miss]   # short percussive monosyllables
phonetic_fingerprint:
  vowel_preference: short-I, short-A, short-E
  attack_profile: hard
  consonant_density: high
structure_preferences:
  preferred_template: pop.standard
  hook_position: chorus-start
  hook_repeats_per_chorus: 2-3
hook_style: percussive-monosyllabic
reference_tracks:
  - "...Baby One More Time"
  - "I Want It That Way"
adoption_prompt: |
  Write in the Max Martin craft mode: 'melodic math' hooks where each chorus
  line's melodic peak lands on a short percussive consonant and a short vowel
  ('it', 'this', 'hit', 'kiss', 'miss'). Pre-chorus tightens cadence and
  shortens note values. Use parallel substitution between verses (one word
  swaps between verse 1 and verse 2). Title is a 2-4 word phrase that scans
  as the strongest cadence in the chorus. Keep imagery low; let the melodic
  contour and consonant attack carry the hook.
```

- [ ] **Step 3: Write Julia Michaels profile (singer-songwriter, conversational craft)**

File: `songwriter/data/songwriters/pop/julia-michaels.yml`

```yaml
slug: julia-michaels
display_name: Julia Michaels
era: 2014-present
primary_genre: pop
role: singer-songwriter
sub_genres: [pop, alt-pop]
notable_credits:
  - "Issues"
  - "Love Myself"
  - "Lonely"
  - "Sorry"
craft_signature:
  - "Conversational verse construction; lines often start mid-thought ('cause I…', 'and I…')."
  - "Specific small admissions: 'I get jealous, I get overwhelmed' — concrete states, not generic 'I feel sad'."
  - "Deliberate vocal hiccup / breath-catch in the demo-style delivery."
  - "Hook is usually a self-diagnosis ('I have issues') rather than a declaration about the other person."
personality_traits: [self-aware, candid, restless, mid-sentence]
writing_style:
  avg_line_syllables: 8
  rhyme_density: medium
  internal_rhyme_freq: low
  end_rhyme_strictness: near-rhyme-friendly
  narrative_mode: conversational-confession
  perspective_default: first-person
  imagery_emphasis: medium
  signature_devices: [mid-sentence-line-starts, self-diagnosis-hook]
preferred_cadences: [melodic-glide, storytelling]
vocab_fingerprint:
  signature_words: [issues, jealous, overwhelmed, anyway, I-mean, kinda, sorta]
  semantic_anchors: [self-state, admission]
  avoided_words: [grand, anthemic, ghost, neon]
phonetic_fingerprint:
  vowel_preference: short-I, short-U
  attack_profile: balanced
  consonant_density: medium
structure_preferences:
  preferred_template: pop.standard
  hook_position: chorus-start
  hook_repeats_per_chorus: 2
hook_style: self-diagnosis
reference_tracks:
  - "Issues"
  - "Lonely"
adoption_prompt: |
  Write in the Julia Michaels craft mode: conversational verses that often
  start mid-thought ('cause I…', 'and I…'). Use specific small self-admissions
  ('I get jealous', 'I get overwhelmed') rather than generic emotional words.
  The hook should be a self-diagnosis about the speaker, not a declaration
  about the other person. Near-rhymes are welcome; perfect rhyme is not
  required. Mid-sentence breath-catches are part of the texture.
```

- [ ] **Step 4: Write Finneas profile (producer-songwriter, intimate-pop)**

File: `songwriter/data/songwriters/pop/finneas.yml`

```yaml
slug: finneas
display_name: Finneas
real_name: Finneas O'Connell
era: 2017-present
primary_genre: pop
role: producer-songwriter
sub_genres: [alt-pop, pop, indie-pop]
notable_credits:
  - "ocean eyes"
  - "bad guy"
  - "everything i wanted"
  - "Happier Than Ever"
craft_signature:
  - "Whisper-to-belt dynamic: verse is close-mic'd intimate, chorus opens up."
  - "Specific household-object imagery ('I'd put my hands up') over abstract metaphor."
  - "Verses often deliver a small narrative scene; chorus delivers the emotional thesis."
  - "Negative-space production cues lyrics — silence between lines is part of the writing."
personality_traits: [observational, restrained, dramaturgical]
writing_style:
  avg_line_syllables: 7
  rhyme_density: low
  internal_rhyme_freq: low
  end_rhyme_strictness: near-rhyme-friendly
  narrative_mode: scene-based
  perspective_default: first-person
  imagery_emphasis: high
  signature_devices: [whisper-to-belt-dynamic, household-imagery, silence-as-punctuation]
preferred_cadences: [melodic-glide, storytelling, hybrid]
vocab_fingerprint:
  signature_words: [hands, eyes, mirror, bedroom, house, kitchen, smaller, quiet]
  semantic_anchors: [household-room, body-part, observation]
  avoided_words: [club, neon, anthem, soldier]
phonetic_fingerprint:
  vowel_preference: short-I, short-A, diphthong
  attack_profile: soft-then-hard-on-chorus
  consonant_density: medium
structure_preferences:
  preferred_template: pop.standard
  hook_position: chorus-mid
  hook_repeats_per_chorus: 2
hook_style: emotional-thesis
reference_tracks:
  - "ocean eyes"
  - "Happier Than Ever"
adoption_prompt: |
  Write in the Finneas craft mode: whisper-to-belt dynamic between verse and
  chorus. Verses are close-mic'd, scene-based, anchored in specific household
  imagery (a kitchen, a hallway, a phone face-down on a counter). Chorus
  delivers the emotional thesis directly. Near-rhymes welcome. Use silence as
  punctuation — lines do not have to fill every beat. Avoid club / anthem
  vocabulary entirely.
```

- [ ] **Step 5: Write Sia profile (self-writing artist, anthemic alt-pop)**

File: `songwriter/data/songwriters/pop/sia.yml`

```yaml
slug: sia
display_name: Sia
real_name: Sia Furler
era: 2000-present
primary_genre: pop
role: self-writing-artist
sub_genres: [pop, alt-pop, dance-pop]
notable_credits:
  - "Chandelier"
  - "Cheap Thrills"
  - "Diamonds (written for Rihanna)"
  - "Pretty Hurts (written for Beyoncé)"
craft_signature:
  - "Vowel-driven hook design: long sustained vowels carry the chorus belt."
  - "Cinematic-physical verbs in verses ('I'm gonna swing from the chandelier')."
  - "Metaphor extended across the entire song rather than reset per section."
  - "Heavy use of present-progressive ('I'm dancing', 'I'm gonna') for forward momentum."
personality_traits: [theatrical, dynamic, unguarded]
writing_style:
  avg_line_syllables: 9
  rhyme_density: medium
  internal_rhyme_freq: medium
  end_rhyme_strictness: near-and-perfect
  narrative_mode: extended-metaphor
  perspective_default: first-person
  imagery_emphasis: high
  signature_devices: [vowel-driven-hook, cinematic-verb, extended-metaphor]
preferred_cadences: [pop-hook, melodic-glide]
vocab_fingerprint:
  signature_words: [tonight, swinging, fly, alive, breathe, hold, fight, weight]
  semantic_anchors: [body-in-motion, single-vivid-image]
  avoided_words: [neon, chrome, midnight, ghost]
  vowel_priority_words: [stay, way, day, fight, fly, alive]
phonetic_fingerprint:
  vowel_preference: long-A, long-I, diphthong
  attack_profile: balanced
  consonant_density: medium
structure_preferences:
  preferred_template: pop.dance
  hook_position: chorus-start
  hook_repeats_per_chorus: 2
hook_style: belt-vowel-anchor
reference_tracks:
  - "Chandelier"
  - "Cheap Thrills"
adoption_prompt: |
  Write in the Sia craft mode: vowel-driven hooks where the title and chorus
  payoff land on long vowels engineered for a belt sustain ('fly', 'stay',
  'fight', 'alive'). Verses use cinematic-physical verbs and present-
  progressive momentum. Carry one extended metaphor across the entire song
  rather than starting fresh per verse.
```

- [ ] **Step 6: Write the failing test**

File: `songwriter/tests/test_seeder_songwriters.py`

```python
import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import (
    genres as genres_seeder,
    songwriter_profiles as sw_seeder,
)


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    genres_seeder.seed(target, DATA_DIR / "genres.yml")
    sw_seeder.seed_directory(target, DATA_DIR / "songwriters")
    return target


def test_pop_songwriters_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        """
        SELECT sp.slug FROM songwriter_profiles sp
        JOIN genres g ON g.id = sp.primary_genre_id
        WHERE g.slug = 'pop'
        """
    ).fetchall()
    slugs = {r["slug"] for r in rows}
    assert {"diane-warren", "max-martin", "julia-michaels", "finneas", "sia"} == slugs


def test_diane_warren_role_is_pure_songwriter(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM songwriter_profiles WHERE slug = 'diane-warren'"
    ).fetchone()
    assert row["role"] == "pure-songwriter"
    cs = json.loads(row["craft_signature"])
    assert isinstance(cs, list)
    assert any("belt" in line.lower() for line in cs)


def test_finneas_role_is_producer_songwriter(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT role FROM songwriter_profiles WHERE slug = 'finneas'"
    ).fetchone()
    assert row["role"] == "producer-songwriter"


def test_adoption_prompt_required(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        "SELECT slug, adoption_prompt FROM songwriter_profiles"
    ).fetchall()
    for r in rows:
        assert r["adoption_prompt"] and len(r["adoption_prompt"]) > 50, r["slug"]
```

- [ ] **Step 7: Run test, verify it fails**

```bash
pytest tests/test_seeder_songwriters.py -v
```

Expected: FAIL.

- [ ] **Step 8: Implement seeder**

File: `songwriter/src/songwriter/seeds/seeders/songwriter_profiles.py`

```python
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
```

- [ ] **Step 9: Run tests, verify they pass**

```bash
pytest tests/test_seeder_songwriters.py -v
```

Expected: 4 PASS.

- [ ] **Step 10: Commit**

```bash
git add data/songwriters/pop src/songwriter/seeds/seeders/songwriter_profiles.py tests/test_seeder_songwriters.py
git commit -m "feat(data): seed 5 pop songwriter profiles (Warren/Martin/Michaels/Finneas/Sia)"
```

---

## Task 22: Songwriter profiles seed — R&B (5 profiles)

**Files:**
- Create: `songwriter/data/songwriters/rnb/frank-ocean.yml`
- Create: `songwriter/data/songwriters/rnb/the-dream.yml`
- Create: `songwriter/data/songwriters/rnb/babyface.yml`
- Create: `songwriter/data/songwriters/rnb/rodney-jerkins.yml`
- Create: `songwriter/data/songwriters/rnb/jam-and-lewis.yml`
- Modify: `songwriter/tests/test_seeder_songwriters.py`

The seeder code is already in place; this task adds data and asserts the role coverage matches Phase 1's success criterion (lens-driven draft variation).

- [ ] **Step 1: Write Frank Ocean profile (self-writing artist, alt-R&B exemplar)**

File: `songwriter/data/songwriters/rnb/frank-ocean.yml`

```yaml
slug: frank-ocean
display_name: Frank Ocean
real_name: Christopher Edwin Breaux
era: 2011-present
primary_genre: rnb
role: self-writing-artist
sub_genres: [alt-rnb, pbrnb]
notable_credits:
  - "Thinkin Bout You"
  - "Pyramids"
  - "Ivy"
  - "Self Control"
  - "Nights"
craft_signature:
  - "Sparse end-rhyme; relies on consonance and vowel echo across non-rhyming line ends."
  - "Time-marker specifics ('Tuesday', 'June'); lets a date or weekday do emotional work that another writer would do with adjectives."
  - "Long-form verse architecture: verses can run 16+ bars before any chorus payoff."
  - "Switches second-person addressee mid-song without flagging the transition."
  - "Concrete second-hand objects (an old camcorder, a watch, a Toyota) anchor abstract longing."
personality_traits: [restrained, observational, time-aware, oblique]
writing_style:
  avg_line_syllables: 11
  rhyme_density: low
  internal_rhyme_freq: low
  end_rhyme_strictness: near-and-vowel-echo-only
  narrative_mode: oblique-confession
  perspective_default: first-person
  imagery_emphasis: high
  signature_devices: [time-marker-anchor, consonance-over-rhyme, mid-song-addressee-shift]
preferred_cadences: [melodic-glide, storytelling, hybrid]
vocab_fingerprint:
  signature_words: [Tuesday, summer, season, eyes, hands, watching, drifting, parking]
  semantic_anchors: [calendar-time, second-hand-object, room]
  avoided_words: [neon, chrome, anthem, soldier, midnight]
phonetic_fingerprint:
  vowel_preference: short-I, short-U, diphthong
  attack_profile: soft
  consonant_density: low-medium
structure_preferences:
  preferred_template: rnb.late-night-drift
  hook_position: chorus-late
  hook_repeats_per_chorus: 1-2
hook_style: oblique-anchor
reference_tracks:
  - "Thinkin Bout You"
  - "Ivy"
adoption_prompt: |
  Write in the Frank Ocean craft mode: sparse rhyme, lots of consonance and
  vowel echo carrying lines that don't end-rhyme. Anchor verses with calendar
  specifics (a Tuesday, a season) and second-hand objects (an old camcorder,
  a parked car). Verses can run long before a chorus arrives. Mid-song
  addressee shifts are allowed and should not be flagged. Avoid 'neon',
  'chrome', anthemic vocabulary, and any AI-bias word in the burn list.
```

- [ ] **Step 2: Write The-Dream profile (producer-songwriter, R&B craft)**

File: `songwriter/data/songwriters/rnb/the-dream.yml`

```yaml
slug: the-dream
display_name: The-Dream
real_name: Terius Youngdell Nash
era: 2007-present
primary_genre: rnb
role: producer-songwriter
sub_genres: [contemporary-rnb, pop, alt-rnb]
notable_credits:
  - "Single Ladies (Put a Ring on It)"
  - "Umbrella"
  - "Holy Grail"
  - "Beautiful Liar"
craft_signature:
  - "Compresses a phrase to its rhythmic essence — tightens a 7-syllable thought into a 4-beat hook."
  - "Stacks one signature word as percussive refrain ('eh-eh', 'oh-oh') as part of the cadence."
  - "Hook architecture is melodic before lyrical — the lyric serves the contour."
  - "Frequent direct-address imperatives in the chorus ('put a ring on it', 'stand under my umbrella')."
personality_traits: [precise, melodic, percussive]
writing_style:
  avg_line_syllables: 6
  rhyme_density: medium
  internal_rhyme_freq: medium
  end_rhyme_strictness: strict-perfect
  narrative_mode: imperative-hook
  perspective_default: first-or-second-person
  imagery_emphasis: low-medium
  signature_devices: [percussive-refrain, imperative-hook, melodic-first-lyric]
preferred_cadences: [pop-hook, punchline]
vocab_fingerprint:
  signature_words: [you, this, now, baby, ring, hands, ay, oh]
  semantic_anchors: [direct-address, simple-imperative]
  avoided_words: [philosophical, abstract, dense]
phonetic_fingerprint:
  vowel_preference: short-I, short-A, diphthong-OI
  attack_profile: hard
  consonant_density: high
structure_preferences:
  preferred_template: rnb.intimate-confession
  hook_position: chorus-start
  hook_repeats_per_chorus: 3
hook_style: imperative-percussive
reference_tracks:
  - "Single Ladies (Put a Ring on It)"
  - "Umbrella"
adoption_prompt: |
  Write in the The-Dream craft mode: melody-first, lyric-second. Compress
  thoughts to their rhythmic essence; a 7-syllable feeling becomes a 4-beat
  hook. Stack a signature percussive vocable ('eh-eh', 'oh-oh') as part of
  the cadence. Chorus uses direct-address imperatives. Strict end-rhymes.
  Keep imagery low; let cadence carry the song.
```

- [ ] **Step 3: Write Babyface profile (pure-songwriter / producer-songwriter, classic R&B)**

File: `songwriter/data/songwriters/rnb/babyface.yml`

```yaml
slug: babyface
display_name: Babyface
real_name: Kenneth Brian Edmonds
era: 1986-present
primary_genre: rnb
role: producer-songwriter
sub_genres: [contemporary-rnb, 90s-rnb, neo-soul]
notable_credits:
  - "End of the Road"
  - "I'll Make Love to You"
  - "Exhale (Shoop Shoop)"
  - "Change the World"
craft_signature:
  - "Long, breath-supporting phrases — verses written for Boyz II Men's collective harmony delivery."
  - "Earnest, plainspoken declarations; uses 'you and me' framing more often than 'I'."
  - "Verses often resolve to a small physical gesture ('I'll make sure you're home', 'I'll be there')."
  - "Bridge typically introduces a metaphor that ties the verse and chorus thematically."
personality_traits: [warm, devotional, traditional, romantic]
writing_style:
  avg_line_syllables: 10
  rhyme_density: medium
  internal_rhyme_freq: low
  end_rhyme_strictness: strict-perfect
  narrative_mode: declarative-devotion
  perspective_default: first-person-plural
  imagery_emphasis: medium
  signature_devices: [collective-we-framing, breath-supporting-phrase, bridge-metaphor]
preferred_cadences: [melodic-glide, storytelling]
vocab_fingerprint:
  signature_words: [we, us, together, never, always, baby, girl, hold, promise]
  semantic_anchors: [partnership, time-together, devotion]
  avoided_words: [neon, club, autotune, edm]
phonetic_fingerprint:
  vowel_preference: long-O, long-A, diphthong
  attack_profile: balanced
  consonant_density: medium
structure_preferences:
  preferred_template: rnb.intimate-confession
  hook_position: chorus-start
  hook_repeats_per_chorus: 2-3
hook_style: declarative-devotion
reference_tracks:
  - "End of the Road"
  - "I'll Make Love to You"
adoption_prompt: |
  Write in the Babyface craft mode: long breath-supporting phrases, earnest
  declarative devotion, 'you and me' / 'we' framing more than 'I'. Verses
  resolve to small physical gestures; bridge introduces a metaphor that ties
  verse and chorus thematically. Strict end-rhymes. Avoid club / EDM
  vocabulary entirely.
```

- [ ] **Step 4: Write Rodney "Darkchild" Jerkins profile (producer-songwriter, 90s/00s R&B)**

File: `songwriter/data/songwriters/rnb/rodney-jerkins.yml`

```yaml
slug: rodney-jerkins
display_name: Rodney Jerkins
real_name: Rodney Roy Jerkins
era: 1996-present
primary_genre: rnb
role: producer-songwriter
sub_genres: [contemporary-rnb, 90s-rnb, pop]
notable_credits:
  - "Say My Name"
  - "It's Not Right but It's Okay"
  - "Heartbreaker"
  - "Telephone"
craft_signature:
  - "Stuttering hook construction — repeats a phoneme or syllable to create rhythmic interest ('say-say-say my name')."
  - "Tempo-locked vocal cadence — the lyric is engineered to ride a specific drum-program pattern."
  - "Confrontational verse content (questioning, accusing) that resolves into a controlled chorus."
  - "Rhythm-section first; the lyric must groove with the pocket or it's rewritten."
personality_traits: [rhythmic, confrontational, pocket-aware]
writing_style:
  avg_line_syllables: 7
  rhyme_density: medium
  internal_rhyme_freq: medium
  end_rhyme_strictness: near-and-perfect
  narrative_mode: confrontation
  perspective_default: first-or-second-person
  imagery_emphasis: low-medium
  signature_devices: [stuttering-hook, tempo-locked-cadence, confrontational-verse]
preferred_cadences: [pop-hook, punchline, straight-4-beat]
vocab_fingerprint:
  signature_words: [say, name, called, who, what, why, told]
  semantic_anchors: [accusation, identification]
  avoided_words: [philosophical, dense, anthem]
phonetic_fingerprint:
  vowel_preference: short-A, short-I, diphthong-EI
  attack_profile: hard
  consonant_density: high
structure_preferences:
  preferred_template: rnb.intimate-confession
  hook_position: chorus-start
  hook_repeats_per_chorus: 2-3
hook_style: stuttering-percussive
reference_tracks:
  - "Say My Name"
  - "It's Not Right but It's Okay"
adoption_prompt: |
  Write in the Rodney Jerkins craft mode: stuttering hook construction
  (repeats a phoneme or syllable). Verses are confrontational (questioning,
  accusing); chorus controls the energy. Lyric must lock to a drum-program
  pattern — engineer the cadence to ride the pocket. Strict-to-near rhymes.
  Keep imagery low and let the rhythm carry.
```

- [ ] **Step 5: Write Jam & Lewis profile (producer-songwriter duo)**

File: `songwriter/data/songwriters/rnb/jam-and-lewis.yml`

```yaml
slug: jam-and-lewis
display_name: Jimmy Jam & Terry Lewis
era: 1981-present
primary_genre: rnb
role: producer-songwriter
sub_genres: [90s-rnb, contemporary-rnb, soul]
notable_credits:
  - "What Have You Done for Me Lately"
  - "Rhythm Nation"
  - "On Bended Knee"
  - "Together Again"
craft_signature:
  - "Long-arc storytelling across the song — verse 1 introduces a problem, verse 2 deepens it, bridge resolves."
  - "Vocal arrangement is part of the writing — leads, ad-libs, and harmony parts are scored on the page."
  - "Hook lyrics often phrase as a question or an ultimatum, never a passive observation."
  - "Strong cadence on the downbeat; offbeat fills used sparingly for dramatic emphasis."
personality_traits: [structural, narrative-arc, harmony-aware]
writing_style:
  avg_line_syllables: 9
  rhyme_density: medium
  internal_rhyme_freq: medium
  end_rhyme_strictness: strict-perfect
  narrative_mode: long-arc-storytelling
  perspective_default: first-or-second-person
  imagery_emphasis: medium
  signature_devices: [arc-across-verses, scored-vocal-arrangement, question-hook]
preferred_cadences: [storytelling, melodic-glide, pop-hook]
vocab_fingerprint:
  signature_words: [what, why, when, again, back, lately, together, tonight]
  semantic_anchors: [accountability, return, partnership]
  avoided_words: [neon, ghost, edm, autotune]
phonetic_fingerprint:
  vowel_preference: short-A, short-E, diphthong
  attack_profile: balanced
  consonant_density: medium
structure_preferences:
  preferred_template: rnb.intimate-confession
  hook_position: chorus-start
  hook_repeats_per_chorus: 2
hook_style: question-or-ultimatum
reference_tracks:
  - "What Have You Done for Me Lately"
  - "On Bended Knee"
adoption_prompt: |
  Write in the Jam & Lewis craft mode: long-arc storytelling — verse 1
  introduces a problem, verse 2 deepens it, bridge resolves. Hook is a
  question or ultimatum, not a passive observation. Score the vocal
  arrangement (lead, ad-libs, harmony) into the lyric — call out where
  ad-libs and harmony parts enter. Strong cadence on the downbeat.
```

- [ ] **Step 6: Add R&B coverage tests**

Append to: `songwriter/tests/test_seeder_songwriters.py`

```python
def test_rnb_songwriters_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        """
        SELECT sp.slug FROM songwriter_profiles sp
        JOIN genres g ON g.id = sp.primary_genre_id
        WHERE g.slug = 'rnb'
        """
    ).fetchall()
    slugs = {r["slug"] for r in rows}
    assert {"frank-ocean", "the-dream", "babyface", "rodney-jerkins", "jam-and-lewis"} == slugs


def test_frank_ocean_role_is_self_writing(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT role FROM songwriter_profiles WHERE slug = 'frank-ocean'"
    ).fetchone()
    assert row["role"] == "self-writing-artist"


def test_total_phase1_profile_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    n = conn.execute("SELECT COUNT(*) AS c FROM songwriter_profiles").fetchone()["c"]
    assert n == 10  # 5 pop + 5 rnb


def test_role_distribution_covers_all_four_kinds(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        "SELECT DISTINCT role FROM songwriter_profiles"
    ).fetchall()
    roles = {r["role"] for r in rows}
    # Phase 1 must demonstrate all 4 role types so the lens-variation criterion
    # is testable.
    expected = {
        "pure-songwriter",
        "producer-songwriter",
        "singer-songwriter",
        "self-writing-artist",
    }
    assert expected <= roles
```

- [ ] **Step 7: Run tests, verify all pass**

```bash
pytest tests/test_seeder_songwriters.py -v
```

Expected: 8 PASS (4 prior + 4 new).

- [ ] **Step 8: Commit**

```bash
git add data/songwriters/rnb tests/test_seeder_songwriters.py
git commit -m "feat(data): seed 5 rnb songwriter profiles + role coverage assertions"
```

---

## Task 23: Sonic descriptor library seed (~10 entries)

**Files:**
- Create: `songwriter/data/descriptors/seeded.yml`
- Create: `songwriter/src/songwriter/seeds/seeders/sonic_descriptors.py`
- Create: `songwriter/tests/test_seeder_descriptors.py`

These are the cache-primer entries for the artist-descriptor cache. Each describes vocal + production characteristics in non-naming terms that can be inlined into a Suno prompt. The artist's name itself never appears in the rendered descriptor.

`source` is `'user-curated'` for all 10 (we wrote them by hand). `quality_state` is `'pinned'` so the descriptor cache prefers them.

- [ ] **Step 1: Write `data/descriptors/seeded.yml`**

File: `songwriter/data/descriptors/seeded.yml`

```yaml
descriptors:
  - canonical_name: Frank Ocean
    era_label: "Channel Orange / Blonde era"
    descriptor_short: "Soft-edged tenor with breath-rich attack, pocketed in dusty Rhodes and muted sub-bass; close-mic intimate, spring-reverb ambience."
    descriptor_long: |
      Soft-edged tenor with breathy attack and a controlled falsetto top. Vocal
      sits very close to the mic, lots of natural lip-and-mouth detail. Production
      leans on dusty Rhodes electric piano, muted sub-bass, sparse programmed drums
      with off-grid percussion, and field-recording textures. Mix is intimate, low
      brightness, narrow-to-medium width, light compression. Spring-reverb and tape
      hiss are part of the texture, not effects added after.
    vocal_attributes:
      gender: male
      range: tenor
      character: soft-edged-with-falsetto-top
      register: head-and-mixed
      attack: breathy
    production_attrs:
      tempo_zone: 60-95
      mix_character: intimate-low-brightness
      instrumentation_cues: [dusty-Rhodes, muted-sub-bass, sparse-programmed-drums, off-grid-percussion]
    genre_context: alt-rnb
    source: user-curated
    quality_state: pinned

  - canonical_name: Adele
    era_label: "21 / 25 era"
    descriptor_short: "Powerhouse alto belt with chest-voice grit; piano-driven big-room production, plate reverb, dramatic dynamic build verse-to-chorus."
    descriptor_long: |
      Powerhouse alto belt with strong chest-voice grit and a controlled head-voice
      crown. Vocal is the production's center; verses are restrained and intimate,
      chorus opens to full belt. Piano-led arrangements with strings, occasional
      drum kit. Big-room plate reverb on vocal and snare. Mix is wide, moderate
      compression, polished but warm. Strong dynamic build verse-to-chorus is the
      production signature.
    vocal_attributes:
      gender: female
      range: alto
      character: powerhouse-belt-with-chest-grit
      register: chest-and-mixed
      attack: full-bodied
    production_attrs:
      tempo_zone: 60-100
      mix_character: warm-wide-polished
      instrumentation_cues: [piano-foundation, string-bed, plate-reverb, drum-kit-on-chorus]
    genre_context: pop-soul
    source: user-curated
    quality_state: pinned

  - canonical_name: Tyla
    era_label: "Tyla / 2023+ era"
    descriptor_short: "Light-airy soprano with rhythmic phrasing; amapiano-pop production with log-drum bass, percussive hat patterns, glossy modern mix."
    descriptor_long: |
      Light-airy soprano with rhythmic phrasing — vocals lock to the groove like
      another percussion instrument. Pronunciation has a soft Southern African
      lilt; melismatic flourishes are short and rhythmic, not extended. Production
      is amapiano-pop crossover: signature log-drum bass, busy percussive hat and
      shaker patterns, glossy contemporary pop mix with bright top-end and tight
      low-end. Vocal sits forward with light plate and short slap-delay throws.
    vocal_attributes:
      gender: female
      range: soprano
      character: light-airy-rhythmic
      register: head-and-mixed
      attack: soft-but-articulated
    production_attrs:
      tempo_zone: 100-115
      mix_character: glossy-bright-tight
      instrumentation_cues: [log-drum-bass, percussive-hat-patterns, shaker, modern-pop-pads]
    genre_context: amapiano-pop
    source: user-curated
    quality_state: pinned

  - canonical_name: SZA
    era_label: "Ctrl / SOS era"
    descriptor_short: "Conversational alto with melismatic ad-libs and falsetto crown; alt-R&B production, finger-snapping percussion, dreamy guitar/Rhodes textures."
    descriptor_long: |
      Conversational alto delivery with frequent melismatic ad-libs and a falsetto
      crown that drops into spoken-word inflection. Vocal sits close-mic with
      light compression and natural breath. Alt-R&B production with finger-snap
      percussion, dreamy clean-guitar arpeggios, soft Rhodes pads, sparse 808
      sub-bass. Mix is medium-bright, medium-wide, light compression. Frequent
      reverb-throw moments on tail words.
    vocal_attributes:
      gender: female
      range: alto
      character: conversational-with-falsetto-crown
      register: chest-mixed-falsetto
      attack: relaxed-natural
    production_attrs:
      tempo_zone: 70-95
      mix_character: medium-bright-wide
      instrumentation_cues: [finger-snap, clean-guitar-arpeggio, Rhodes-pads, 808-sub]
    genre_context: alt-rnb
    source: user-curated
    quality_state: pinned

  - canonical_name: Olivia Rodrigo
    era_label: "SOUR / GUTS era"
    descriptor_short: "Conversational soprano with vulnerable verse / belted chorus; alt-pop band production, distorted guitars on chorus, dry close-mic verses."
    descriptor_long: |
      Conversational soprano with a vulnerable verse delivery and a belted chorus.
      Vocal flips to a slight rasp on chorus peaks. Verses are dry and very
      close-mic'd; chorus opens to band production with distorted electric guitars,
      live drum kit, and natural plate reverb. Pop-rock crossover energy. Mix is
      mid-bright, moderate compression, medium-wide, deliberately scrappier than
      mainstream-pop polish.
    vocal_attributes:
      gender: female
      range: soprano
      character: conversational-to-belted-rasp
      register: chest-and-mixed
      attack: soft-verse-hard-chorus
    production_attrs:
      tempo_zone: 80-130
      mix_character: mid-bright-medium-wide
      instrumentation_cues: [distorted-electric-guitars, live-drum-kit, natural-plate-reverb]
    genre_context: alt-pop
    source: user-curated
    quality_state: pinned

  - canonical_name: The Weeknd
    era_label: "Beauty Behind the Madness / After Hours era"
    descriptor_short: "Tenor with falsetto top; 80s-inflected synth-pop production, gated reverb snare, lush analog pads, wide stadium mix."
    descriptor_long: |
      Tenor lead with a strong falsetto top and a velvety mid-range. Vocal phrasing
      is melismatic but controlled. Production borrows heavily from 80s synth-pop:
      gated-reverb snares, lush analog pads, monosynth basslines, occasional sax-
      like leads. Mix is wide and stadium-ready, brightness is medium-high, heavy
      compression for radio-loud feel. Doubled lead vocal in chorus, plate reverb
      on tail words.
    vocal_attributes:
      gender: male
      range: tenor
      character: velvety-with-falsetto
      register: chest-mixed-falsetto
      attack: balanced
    production_attrs:
      tempo_zone: 90-115
      mix_character: wide-stadium-bright
      instrumentation_cues: [gated-reverb-snare, analog-pads, monosynth-bass, doubled-vocal]
    genre_context: synth-pop-rnb
    source: user-curated
    quality_state: pinned

  - canonical_name: Phoebe Bridgers
    era_label: "Stranger in the Alps / Punisher era"
    descriptor_short: "Soft soprano spoken-sung delivery; indie-folk production, fingerpicked guitar, brushed drums, room-mic ambience, very dry vocal."
    descriptor_long: |
      Soft soprano with a spoken-sung delivery — barely-projected verses,
      restrained chorus. Vocal is very dry and close-mic'd, almost no reverb.
      Production is indie-folk: fingerpicked acoustic guitar, brushed drums,
      occasional pedal-steel or muted electric. Strings or horns appear on
      bridges. Mix is low-brightness, light compression, narrow-to-medium width,
      heavy room-mic ambience.
    vocal_attributes:
      gender: female
      range: soprano
      character: spoken-sung-restrained
      register: head-mixed
      attack: very-soft
    production_attrs:
      tempo_zone: 70-105
      mix_character: low-brightness-room-ambient
      instrumentation_cues: [fingerpicked-acoustic, brushed-drums, pedal-steel, room-mic]
    genre_context: indie-folk
    source: user-curated
    quality_state: pinned

  - canonical_name: Drake
    era_label: "Take Care / Nothing Was the Same era"
    descriptor_short: "Conversational baritone-tenor with melodic singing; trap-R&B production, 808 sub-bass, sparse hat patterns, dark cinematic atmosphere."
    descriptor_long: |
      Conversational baritone-tenor that swaps freely between rapped and sung
      delivery within the same verse. Vocal is double-tracked in choruses,
      single-tracked in verses, with frequent ad-lib responses panned wide. Trap-
      R&B production: deep 808 sub-bass, sparse programmed hat patterns, dark
      atmospheric pads. Mix is low-medium brightness, moderate compression, wide.
      Reverb-throw moments on tail words; otherwise vocal is mostly dry.
    vocal_attributes:
      gender: male
      range: baritone-tenor
      character: conversational-rapped-and-sung
      register: chest-mixed
      attack: relaxed
    production_attrs:
      tempo_zone: 70-90
      mix_character: low-medium-bright-dark-atmospheric
      instrumentation_cues: [808-sub, sparse-hat-pattern, atmospheric-pads, ad-lib-pans]
    genre_context: trap-rnb
    source: user-curated
    quality_state: pinned

  - canonical_name: Beyoncé
    era_label: "Lemonade era"
    descriptor_short: "Powerhouse mezzo with belt grit and falsetto crown; genre-fluid production, live and programmed drums layered, bold dynamic shifts."
    descriptor_long: |
      Powerhouse mezzo with belt grit, a controlled falsetto crown, and full
      melismatic technique. Production is genre-fluid (R&B, rock, country, gospel)
      depending on song. Live and programmed drums layered. Strong dynamic shifts
      between verse and chorus, sometimes mid-line. Wide mix, moderate-to-heavy
      compression, mid-high brightness. Vocal is the dominant element — multiple
      stacked harmonies in choruses.
    vocal_attributes:
      gender: female
      range: mezzo
      character: powerhouse-belt-with-falsetto-and-melisma
      register: chest-mixed-falsetto
      attack: full-bodied-controlled
    production_attrs:
      tempo_zone: 70-130
      mix_character: wide-mid-bright-dynamic
      instrumentation_cues: [layered-live-and-programmed-drums, stacked-harmonies, hybrid-genre-instrumentation]
    genre_context: rnb-pop-rock
    source: user-curated
    quality_state: pinned

  - canonical_name: Billie Eilish
    era_label: "When We All Fall Asleep / Happier Than Ever era"
    descriptor_short: "Whispered soprano close-mic'd vocal; minimal alt-pop production, sub-bass, finger-snap percussion, occasional belt chorus payoff."
    descriptor_long: |
      Whispered soprano with extreme close-mic intimacy — natural breath, lip,
      and mouth detail audible. Vocals are heavily close-compressed but very dry.
      Production is minimal alt-pop: deep sub-bass, finger-snap or programmed
      percussion, sparse synth textures. Occasional belt chorus payoff but most
      delivery stays in whisper register. Mix is medium width, low brightness,
      heavy compression on vocal, very little ambience.
    vocal_attributes:
      gender: female
      range: soprano
      character: whispered-close-mic
      register: head-mixed
      attack: extremely-soft
    production_attrs:
      tempo_zone: 80-110
      mix_character: low-brightness-medium-width-dry
      instrumentation_cues: [deep-sub-bass, finger-snap, sparse-synth, close-mic-vocal]
    genre_context: alt-pop
    source: user-curated
    quality_state: pinned
```

- [ ] **Step 2: Write the failing test**

File: `songwriter/tests/test_seeder_descriptors.py`

```python
import json

from songwriter.seeds import db as db_module, DATA_DIR
from songwriter.seeds.seeders import sonic_descriptors as desc_seeder


def _setup(tmp_path):
    target = tmp_path / "test.db"
    db_module.init_db(target)
    desc_seeder.seed(target, DATA_DIR / "descriptors" / "seeded.yml")
    return target


def test_seed_descriptors_count(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM artist_descriptor_cache"
    ).fetchone()["c"]
    assert n == 10


def test_seed_descriptors_normalizes_name(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    row = conn.execute(
        "SELECT * FROM artist_descriptor_cache WHERE normalized_name = 'frank ocean'"
    ).fetchone()
    assert row is not None
    assert row["canonical_name"] == "Frank Ocean"
    assert row["source"] == "user-curated"
    assert row["quality_state"] == "pinned"


def test_seed_descriptors_short_is_under_30_words(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        "SELECT canonical_name, descriptor_short FROM artist_descriptor_cache"
    ).fetchall()
    for r in rows:
        n = len(r["descriptor_short"].split())
        assert n <= 30, f"{r['canonical_name']}: descriptor_short has {n} words"


def test_seed_descriptors_no_artist_name_inside_descriptor(tmp_path):
    target = _setup(tmp_path)
    conn = db_module.connect(target)
    rows = conn.execute(
        "SELECT canonical_name, descriptor_short, descriptor_long FROM artist_descriptor_cache"
    ).fetchall()
    for r in rows:
        # the canonical name must not appear inside the rendered descriptors
        assert r["canonical_name"].lower() not in r["descriptor_short"].lower(), r["canonical_name"]
        assert r["canonical_name"].lower() not in r["descriptor_long"].lower(), r["canonical_name"]
```

- [ ] **Step 3: Run test, verify it fails**

```bash
pytest tests/test_seeder_descriptors.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement seeder**

File: `songwriter/src/songwriter/seeds/seeders/sonic_descriptors.py`

```python
import json
import re
from pathlib import Path

from songwriter.seeds import db as db_module
from songwriter.seeds.yaml_loader import load_yaml, require_keys


_HONORIFICS = re.compile(r"\b(mr|mrs|ms|the|dj)\b\.?", re.IGNORECASE)


def _normalize(name: str) -> str:
    s = _HONORIFICS.sub("", name).strip().lower()
    s = re.sub(r"[^\w\s]", "", s)         # strip punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s


def seed(db_path: Path, yaml_path: Path) -> None:
    data = load_yaml(yaml_path)
    require_keys(data, ["descriptors"], context=str(yaml_path))
    conn = db_module.connect(db_path)
    try:
        for d in data["descriptors"]:
            require_keys(
                d,
                ["canonical_name", "descriptor_short", "descriptor_long", "source"],
                context=f"{yaml_path}#{d.get('canonical_name')}",
            )
            normalized = _normalize(d["canonical_name"])
            descriptor = d.get("descriptor") or d["descriptor_short"]
            conn.execute(
                """
                INSERT INTO artist_descriptor_cache
                  (normalized_name, canonical_name, era_label,
                   descriptor, descriptor_short, descriptor_long,
                   vocal_attributes, production_attrs, genre_context,
                   source, quality_state)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(normalized_name) DO UPDATE SET
                    canonical_name = excluded.canonical_name,
                    era_label = excluded.era_label,
                    descriptor = excluded.descriptor,
                    descriptor_short = excluded.descriptor_short,
                    descriptor_long = excluded.descriptor_long,
                    vocal_attributes = excluded.vocal_attributes,
                    production_attrs = excluded.production_attrs,
                    genre_context = excluded.genre_context,
                    source = excluded.source,
                    quality_state = excluded.quality_state
                """,
                (
                    normalized, d["canonical_name"], d.get("era_label"),
                    descriptor, d["descriptor_short"], d["descriptor_long"],
                    json.dumps(d.get("vocal_attributes") or {}),
                    json.dumps(d.get("production_attrs") or {}),
                    d.get("genre_context"),
                    d["source"], d.get("quality_state", "unverified"),
                ),
            )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_seeder_descriptors.py -v
```

Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add data/descriptors src/songwriter/seeds/seeders/sonic_descriptors.py tests/test_seeder_descriptors.py
git commit -m "feat(data): seed 10 sonic descriptors (cache primer, all pinned)"
```

---

## Task 24: Top-level build orchestrator

**Files:**
- Create: `songwriter/src/songwriter/seeds/build.py`
- Create: `songwriter/tests/test_build_integration.py`

The orchestrator wires every seeder in dependency order: schema → words → genres → cadence → structure → production → emotion-tempo → burn → vocab → songwriters → descriptors. It downloads CMUdict on first run and reuses the cached copy thereafter.

- [ ] **Step 1: Write the failing test**

File: `songwriter/tests/test_build_integration.py`

```python
"""End-to-end build integration test using a small CMUdict fixture."""
from pathlib import Path

import pytest

from songwriter.seeds import build as build_module
from songwriter.seeds import db as db_module


FIXTURE_CMUDICT = (
    Path(__file__).parent / "fixtures" / "cmudict_vocab_words.txt"
)


def test_full_build_produces_populated_db(tmp_path, monkeypatch):
    target_db = tmp_path / "songwriter.db"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # Pre-seed the cache with our small fixture so build never hits the network
    fake_cmudict = cache_dir / "cmudict.dict"
    fake_cmudict.write_text(FIXTURE_CMUDICT.read_text())

    build_module.run(db_path=target_db, cache_dir=cache_dir)

    conn = db_module.connect(target_db)
    counts = {
        t: conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        for t in [
            "words", "genres", "sub_genres", "cadence_patterns",
            "structure_templates", "production_fingerprints",
            "emotion_tempo_map", "suno_burn_list",
            "vocab_banks", "vocab_bank_words",
            "songwriter_profiles", "artist_descriptor_cache",
        ]
    }
    assert counts["genres"] == 12
    assert counts["cadence_patterns"] == 10
    assert counts["structure_templates"] == 4
    assert counts["production_fingerprints"] == 11
    assert counts["emotion_tempo_map"] >= 20
    assert counts["suno_burn_list"] >= 50
    assert counts["vocab_banks"] == 12   # 6 pop + 6 rnb
    assert counts["vocab_bank_words"] >= 100
    assert counts["songwriter_profiles"] == 10
    assert counts["artist_descriptor_cache"] == 10


def test_build_is_idempotent(tmp_path):
    target_db = tmp_path / "songwriter.db"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "cmudict.dict").write_text(FIXTURE_CMUDICT.read_text())

    build_module.run(db_path=target_db, cache_dir=cache_dir)
    build_module.run(db_path=target_db, cache_dir=cache_dir)

    conn = db_module.connect(target_db)
    n = conn.execute("SELECT COUNT(*) AS c FROM songwriter_profiles").fetchone()["c"]
    assert n == 10
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_build_integration.py -v
```

Expected: FAIL — `build_module.run` doesn't exist.

- [ ] **Step 3: Implement orchestrator**

File: `songwriter/src/songwriter/seeds/build.py`

```python
"""Top-level build orchestrator. Run via `songwriter-build` or `python -m songwriter.seeds.build`."""

import argparse
import time
from pathlib import Path

from songwriter.seeds import (
    DATA_DIR, CACHE_DIR, DB_PATH,
    cmudict, db as db_module,
)
from songwriter.seeds.seeders import (
    words as words_seeder,
    genres as genres_seeder,
    cadence_patterns as cadence_seeder,
    structure_templates as struct_seeder,
    production_fingerprints as prod_seeder,
    emotion_tempo_map as et_seeder,
    burn_list as burn_seeder,
    vocab_banks as vocab_seeder,
    songwriter_profiles as sw_seeder,
    sonic_descriptors as desc_seeder,
)


def _step(label: str, fn) -> None:
    t0 = time.time()
    fn()
    dt = time.time() - t0
    print(f"  {label:<32}  {dt:6.2f}s")


def run(*, db_path: Path | None = None, cache_dir: Path | None = None) -> None:
    db_path = db_path or DB_PATH
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cmudict_path = cache_dir / "cmudict.dict"

    print(f"Building {db_path} ...")
    print("STEP                              TIME")
    print("-" * 42)

    _step("init_db", lambda: db_module.init_db(db_path))
    _step("download_cmudict", lambda: cmudict.download(cmudict_path))
    _step("seed_words", lambda: words_seeder.seed_from_cmudict(db_path, cmudict_path))
    _step("seed_genres", lambda: genres_seeder.seed(db_path, DATA_DIR / "genres.yml"))
    _step("seed_cadence", lambda: cadence_seeder.seed(db_path, DATA_DIR / "cadence_patterns.yml"))
    _step("seed_structure", lambda: struct_seeder.seed(db_path, DATA_DIR / "structure_templates.yml"))
    _step("seed_production", lambda: prod_seeder.seed(db_path, DATA_DIR / "production_fingerprints.yml"))
    _step("seed_emotion_tempo", lambda: et_seeder.seed(db_path, DATA_DIR / "emotion_tempo_map.yml"))
    _step("seed_burn_list", lambda: burn_seeder.seed(db_path, DATA_DIR / "burn_list.yml"))
    _step("seed_vocab", lambda: vocab_seeder.seed_directory(db_path, DATA_DIR / "vocab"))
    _step("seed_songwriters", lambda: sw_seeder.seed_directory(db_path, DATA_DIR / "songwriters"))
    _step("seed_descriptors", lambda: desc_seeder.seed(db_path, DATA_DIR / "descriptors" / "seeded.yml"))

    print(f"\nBuild complete: {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build songwriter.db")
    parser.add_argument("--db", type=Path, default=None, help="Override DB output path")
    parser.add_argument("--cache", type=Path, default=None, help="Override CMUdict cache dir")
    args = parser.parse_args()
    run(db_path=args.db, cache_dir=args.cache)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_build_integration.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Run the full build against the real CMUdict (smoke check)**

```bash
songwriter-build
```

Expected output: each step prints with timing; final line `Build complete: .../data/songwriter.db`. The CMUdict download is one-time; second invocation reuses the cached file.

- [ ] **Step 6: Manual sanity query the built DB**

```bash
sqlite3 data/songwriter.db "SELECT COUNT(*) FROM words"
sqlite3 data/songwriter.db "SELECT slug, role FROM songwriter_profiles"
sqlite3 data/songwriter.db "SELECT slug FROM vocab_banks"
```

Expected: words ≥ 125000; 10 songwriter profiles; 12 vocab banks (pop + rnb).

- [ ] **Step 7: Commit**

```bash
git add src/songwriter/seeds/build.py tests/test_build_integration.py
git commit -m "feat(data): wire top-level build orchestrator + integration test"
```

---

## Task 25: Full-suite test sweep + lint pass

**Files:** none

- [ ] **Step 1: Run the entire test suite**

```bash
pytest -q
```

Expected: all tests pass with no warnings about missing fixtures, unclosed connections, or deprecated APIs.

- [ ] **Step 2: Verify the build is reproducible**

```bash
rm -f data/songwriter.db
songwriter-build
sqlite3 data/songwriter.db "SELECT COUNT(*) FROM songwriter_profiles"
# Expected: 10
sqlite3 data/songwriter.db "SELECT COUNT(*) FROM artist_descriptor_cache"
# Expected: 10
sqlite3 data/songwriter.db "SELECT COUNT(*) FROM words" | awk '$1 >= 125000 { print "OK"; exit } { print "TOO FEW:", $1; exit 1 }'
```

- [ ] **Step 3: Verify the DB file is not tracked by git**

```bash
git status --short data/songwriter.db
```

Expected: empty output (file is gitignored).

- [ ] **Step 4: If any test fails or any verification fails, fix and recommit before moving on. No new commit needed if everything passes.**

---

## Task 26: Contributor README

**Files:**
- Create: `songwriter/data/README.md`

This is the docs the next person (or future-you, or the FastAPI sub-plan author) reads to understand how to add new banks, profiles, or descriptors without needing to read the seeder code.

- [ ] **Step 1: Write `data/README.md`**

File: `songwriter/data/README.md`

```markdown
# Songwriter data layer

This directory holds the human-editable source for `songwriter.db`. The build
script (`songwriter-build`) compiles everything here, plus CMUdict for the
phonetic master index, into a single SQLite file.

## Adding a new vocab bank

1. Pick a slug like `<genre>.<theme>` (e.g., `pop.confession`).
2. Create `data/vocab/<genre>/<theme>.yml` with:
   ```yaml
   slug: pop.confession
   name: Pop / Confession
   description: <one sentence>
   words:
     - { word: voicemail, emotional_weight: 0.8, imagery_class: physical }
     - { word: receipt,   emotional_weight: 0.7, imagery_class: physical }
   ```
3. `imagery_class` is one of: `sensory`, `abstract`, `physical`, `metaphorical`.
4. Add `cliche_flag: true` for words you want flagged but not removed (the
   skill warns when a draft uses one).
5. Add `ai_bias_flag: true` for words on the Suno burn list (the prompt-builder
   strips them automatically).
6. Run `songwriter-build` to recompile. New words missing from CMUdict get
   IPA via gruut automatically.

## Adding a new songwriter profile

1. Pick a slug like `<first-last>` (e.g., `julia-michaels`).
2. Create `data/songwriters/<genre>/<slug>.yml`. Required keys: `slug`,
   `display_name`, `role`, `primary_genre`, `adoption_prompt`.
3. `role` is one of: `pure-songwriter`, `producer-songwriter`,
   `singer-songwriter`, `self-writing-artist`. Choose carefully — this drives
   how the skill applies the lens during drafting.
4. `craft_signature` is a list of plain-English mechanics observations
   ('always end-rhymes on long vowels', 'mid-line breath catches'). The
   skill reads these directly during the lens-application step.
5. `adoption_prompt` is the actual system-prompt addition the skill loads
   when this lens is active. Write it as direct instructions to the writer.
6. `notable_credits` and `reference_tracks` should be **titles only** — never
   include lyric content. Copyright safety.
7. Run `songwriter-build` to recompile.

## Adding a new sonic descriptor

1. Edit `data/descriptors/seeded.yml` and add an entry under `descriptors:`.
2. Required: `canonical_name`, `descriptor_short` (≤30 words),
   `descriptor_long` (~80-100 words), `source`, `quality_state`.
3. `source` is one of: `auto-llm`, `songwriter-profile-derived`,
   `user-curated`. For hand-written entries, use `user-curated` and set
   `quality_state: pinned` so the cache prefers them.
4. **Never** include the artist's name inside `descriptor_short` or
   `descriptor_long`. Tests enforce this. The point of the descriptor system
   is name-free Suno prompts.
5. Run `songwriter-build` to recompile.

## Adding a new burn-list entry

1. Edit `data/burn_list.yml` and add to `words:`.
2. `severity` is one of: `mild`, `strong`, `extreme`.
3. `alternatives` is a list of replacement phrases the prompt-builder can
   substitute. Include at least 3.

## Rebuilding from scratch

```bash
rm -f data/songwriter.db data/cache/cmudict.dict
songwriter-build
```

Total build time on a current laptop: ~10-30 seconds (mostly CMUdict download
on first run; ~5 seconds on rebuild).
```

- [ ] **Step 2: Commit**

```bash
git add data/README.md
git commit -m "docs(data): add contributor README for vocab / songwriters / descriptors"
```

---

## Self-review summary

**Spec coverage (data-layer scope only):**

| Spec deliverable | Task |
|---|---|
| Complete DB schema + migration scripts | 2, 3 |
| CMUdict ingestion + IPA derivation | 4, 5, 9, 11 |
| gruut English IPA fallback | 10 |
| Phonetic derivations (syllables, stress, rhyme class, vowel shape, attack, density) | 6, 7, 8 |
| 12 genres + sub-genre tree (Pop+R&B fully expanded, others shipped at parent depth) | 13 |
| 10 cadence patterns | 14 |
| Pop + R&B structure templates | 15 |
| Pop + R&B production fingerprints (11 sub-genres) | 16 |
| Emotion-tempo map for intent-mismatch prevention (≥20 entries) | 17 |
| Suno burn list (~50 entries) | 18 |
| 6 Pop vocab banks + 6 R&B vocab banks (~200 curated words) | 19, 20 |
| 5 Pop + 5 R&B songwriter profiles, all 4 role types represented | 21, 22 |
| 10 pre-seeded sonic descriptors (cache primer, all pinned) | 23 |
| Top-level build orchestrator | 24 |
| Full-suite verification + reproducibility check | 25 |
| Contributor README | 26 |

**Out of scope for this plan (handled by sister plans):**
- The 5 validation rule engines run in production — that's the FastAPI plan.
- The descriptor cache HIT/MISS pipeline (auto-LLM on miss, descriptor short splice into Suno prompts) — that's the skill plan, and it consumes the `artist_descriptor_cache` table this plan ships.
- Multilingual phonetics (Spanish, Yoruba, Igbo, Pidgin, London-slang) and remaining 10 genres' content — Phase 2.
- WikiPron fallback layer — Phase 2.

**Known approximations:**
- Stress digits 1 and 2 both map to "stressed" in `stress_pattern` (we don't distinguish primary vs secondary stress in the rhyme/cadence layer; refining this is Phase 2).
- ARPAbet→IPA mapping is the standard table — not phonetician-grade for every dialect; sufficient for songwriting craft work.
- gruut's English IPA varies for slang and proper nouns; words missing from CMUdict that gruut also struggles with will get `ipa=""` rather than a guess. The vocab seeder logs these (visible in build output).

**Critical assertions the plan tests:**
1. Schema applies cleanly and exposes all 12 expected tables (Task 2).
2. CMUdict-derived `words.rhyme_class` for "love" and "above" matches (rhyme detection works) (Tasks 7, 11).
3. All 4 songwriter-role types are represented in the seed (Task 22) — required so Phase 1 success criterion #4 ("lens produces visibly different draft") is measurable.
4. Sonic descriptors never embed the artist's canonical name in their rendered text (Task 23) — required so the Suno prompt-builder can splice descriptors without leaking names.
5. Full build is idempotent (Task 24) — running twice produces the same DB.
6. Vocab banks resolve every word against the `words` table, falling back to gruut for slang/coinage (Task 19).

**Type/name consistency check:** All seeders expose either `seed(db_path, yaml_path)` or `seed_directory(db_path, dir_path)`. The words seeder exposes `seed_from_cmudict(db_path, cmudict_path)`. Helpers use a stable namespace: `db_module.{init_db, connect}`, `derived.{syllable_count, stress_pattern, rhyme_class, vowel_shape, first_syllable_attack, consonant_density, syllable_count_class}`, `phonemes.{is_vowel, is_consonant, is_hard_consonant, attack_class, vowel_shape_label}`, `arpabet_ipa.{arpabet_to_ipa, strip_stress}`, `cmudict.{download, parse_file}`, `gruut_fallback.{ipa_for_word}`, `yaml_loader.{load_yaml, load_all_in, require_keys}`.

---

## Execution handoff

This plan is structured for either execution mode. Subagent-driven is recommended given the 26-task scope and to keep the main session's context window clean across multiple sessions. Each task is self-contained — a fresh subagent reading just one task should have everything it needs to implement, test, and commit it.

The sister sub-plans (FastAPI, Skill, Web UI) should be written only **after** this plan is executed end-to-end, since they consume the schema and seed shapes defined here.


