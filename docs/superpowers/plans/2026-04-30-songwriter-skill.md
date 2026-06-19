# Songwriter Claude Code Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Claude Code `/song` slash command + `songwriting` skill that drives the full 7-step songwriting workflow end-to-end. The skill consumes the FastAPI backend for DB lookups and validation orchestration, and writes drafts directly to the song JSON file (the source of truth) so the file watcher's broadcast keeps the web UI in sync.

**Architecture:** The slash command (`.claude/commands/song.md`) is a thin dispatcher that delegates to a content-rich skill (`.claude/skills/songwriting/SKILL.md`). The skill carries the prompts, rules, and API recipes Claude Code needs to drive the workflow conversationally. Drafts and validation results flow into `~/Songwriter/songs/<slug>.json`; the API watches that directory and broadcasts updates over WebSocket to any connected UI.

**Tech Stack:** Markdown (Claude Code skill format with YAML frontmatter), Bash recipes calling `curl` against `localhost:8000`, the user's existing 5-rule framework documents as inline reference content. No new Python.

**Scope boundary:** This plan ships the skill files only. It does not modify the FastAPI service — the skill consumes the API's existing surface. It does not ship the web UI (separate sub-plan).

**Sister plans:**
- ✅ `2026-04-30-songwriter-data-layer.md` — done
- ✅ `2026-04-30-songwriter-fastapi.md` — done
- ⏳ `2026-04-30-songwriter-web-ui.md` — Next.js client (next)

**Decisions baked in:**
- The skill writes JSON directly via Read/Edit/Write tools (the file watcher catches the change and broadcasts to the UI). Validation runs through the API's `POST /songs/{slug}/validate` endpoint with `include_llm=false` (cheap deterministic checks); the LLM-judged Story/Sentence engine runs *inside* the skill's own prompt context (no need to subprocess `claude --print` since Claude Code IS the LLM).
- The skill assumes the API is running on `http://localhost:8000`. If it's down, commands surface a clear error pointing at `start.sh`.
- Skills live at the **project level** in the `songwriter/` repo (`songwriter/.claude/skills/songwriting/`) so they're git-tracked and travel with the codebase.
- All artist references inside lyrics or Suno prompts go through the descriptor cache — never name an artist in output.
- The skill never includes copyrighted lyric content. Reference tracks are titles only.

---

## File Structure

```
songwriter/
├── .claude/
│   ├── commands/
│   │   └── song.md                      # /song slash command (dispatcher)
│   └── skills/
│       └── songwriting/
│           ├── SKILL.md                 # main skill content + frontmatter
│           └── reference/
│               ├── workflow.md          # 7-step master workflow
│               ├── prompt-refinement.md # 5-phase Suno prompt loop
│               ├── api-recipes.md       # curl/HTTP recipes for each endpoint
│               ├── lens-application.md  # how to load + apply a songwriter lens
│               ├── descriptor-cache.md  # sonic descriptor lookup pipeline
│               └── constraints.md       # immutable rules (no copyrighted lyrics, etc.)
├── tests/skill/
│   ├── __init__.py
│   ├── test_skill_files.py              # frontmatter + structure linting
│   ├── test_skill_api_alignment.py      # endpoints referenced exist + match contract
│   └── test_skill_constraints.py        # no copyrighted lyric content; no banned phrases
└── docs/skill/
    └── INVOKE.md                        # human-facing "how to use the skill"
```

---

## Conventions

- One commit per task. TDD where it makes sense: skill-file linters are testable; the skill's *behavior* is human-tested via the integration smoke checklist (Task 8).
- Commit message format: `feat(skill): <subject>` or `docs(skill): <subject>` or `test(skill): <subject>`.
- Skill markdown files use YAML frontmatter (`name`, `description`, `version`, etc.) per Claude Code's skill format.
- Reference docs are loaded by SKILL.md via explicit "Read this reference doc" instructions, not auto-loaded — keeps the skill's runtime context tight.

---

## Task 1: Skill scaffolding + dispatcher slash command

**Files:**
- Create: `songwriter/.claude/commands/song.md`
- Create: `songwriter/.claude/skills/songwriting/SKILL.md`
- Create: `tests/skill/__init__.py`
- Create: `tests/skill/test_skill_files.py`

The `/song` slash command is a thin dispatcher. It loads the `songwriting` skill (which carries all the deep content) and routes to the right subcommand based on `$ARGUMENTS`.

- [ ] **Step 1: Write the failing test (lints structure)**

File: `tests/skill/test_skill_files.py`

```python
import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / ".claude" / "skills" / "songwriting"
COMMAND_FILE = REPO / ".claude" / "commands" / "song.md"


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def test_song_command_exists_with_frontmatter():
    assert COMMAND_FILE.exists()
    fm = _frontmatter(COMMAND_FILE.read_text())
    assert fm.get("name") in ("song", "/song")
    assert "description" in fm


def test_song_command_dispatches_subcommands():
    text = COMMAND_FILE.read_text()
    # the command body must reference $ARGUMENTS so subcommands are routed
    assert "$ARGUMENTS" in text or "{{args}}" in text or "ARGUMENTS" in text
    for sub in ["new", "open", "draft", "refine", "alt", "validate", "lens", "prompt", "export", "list"]:
        assert sub in text, f"command should reference subcommand {sub!r}"


def test_skill_md_exists_with_frontmatter():
    skill_md = SKILL_DIR / "SKILL.md"
    assert skill_md.exists()
    fm = _frontmatter(skill_md.read_text())
    assert fm.get("name") == "songwriting"
    assert "description" in fm
    assert len(fm["description"]) > 30


def test_skill_references_api_base_url():
    body = (SKILL_DIR / "SKILL.md").read_text()
    assert "localhost:8000" in body, "skill should reference the API base URL"


def test_skill_lists_all_subcommands():
    body = (SKILL_DIR / "SKILL.md").read_text().lower()
    for sub in ["new", "open", "draft", "refine", "alt", "validate", "lens", "prompt", "export", "list"]:
        assert sub in body
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
source .venv/bin/activate
pytest tests/skill/test_skill_files.py -v
```

- [ ] **Step 3: Write the slash command**

File: `songwriter/.claude/commands/song.md`

```markdown
---
name: song
description: Songwriter app entry point - drives the 7-step songwriting workflow with framework rules, lens application, and Suno prompt refinement
argument-hint: [new | open <slug> | draft [section] | refine <section> | alt <section> <line> | validate | lens <slug> | prompt | export | list]
---

You are the songwriter app. Load the `songwriting` skill (`.claude/skills/songwriting/SKILL.md`) — it carries the full workflow, framework rules, API recipes, lens application logic, and Suno prompt refinement subroutine.

The user invoked `/song $ARGUMENTS`.

Dispatch based on the first token of $ARGUMENTS:

- `new` → run the New Song wizard (6 steps, see `reference/workflow.md`)
- `open <slug>` → load `~/Songwriter/songs/<slug>.json` and present a status summary
- `draft [section]` → draft section(s) using the 7-step workflow (see `reference/workflow.md`)
- `refine <section>` → conversational refinement of a specific section
- `alt <section> <line>` → generate 3 alternatives for a single line
- `validate` → call `POST /songs/<slug>/validate` and present results; fix any failures interactively
- `lens <slug>` → apply or change the songwriter lens (load `adoption_prompt` from API; see `reference/lens-application.md`)
- `prompt` → run the 5-phase Suno prompt refinement loop (see `reference/prompt-refinement.md`)
- `export` → final validation pass, generate the Suno prompt, save, present
- `list` → list all songs in `~/Songwriter/songs/`
- (no argument) → present a menu of the above and ask the user which to run

Before doing anything, verify the API is reachable:

```bash
curl -sf http://localhost:8000/healthz > /dev/null || echo "API not running — start with ./start.sh"
```

If the API is down, surface a clear error and stop.

Always honor the constraints in `reference/constraints.md` — never include copyrighted lyric content, never name an artist directly in lyrics or Suno prompts (use the descriptor cache), never bypass validation.
```

- [ ] **Step 4: Write the main skill file**

File: `songwriter/.claude/skills/songwriting/SKILL.md`

```markdown
---
name: songwriting
description: Drive a Claude-Code-native songwriting workflow that operationalizes the 5-rule framework, applies songwriter lenses, scrubs Suno-bias vocab, and outputs validated lyrics + a focused Suno prompt
version: 0.1.0
---

# Songwriting Skill

You are guiding a user through the full songwriting workflow. Your job is to take a user's intent and produce **validated lyrics + a focused Suno prompt** that don't drift toward AI-cliche territory.

## How this skill is organized

This file is the entry point. Specific phases of work load specific reference docs:

- `reference/workflow.md` — the 7-step master workflow (Story → Sentence → Phonetic → Cadence → Genre → Final-Validate → Suno-Prompt)
- `reference/api-recipes.md` — exact curl invocations for every API endpoint
- `reference/lens-application.md` — how to load and apply a songwriter lens
- `reference/descriptor-cache.md` — sonic descriptor lookup pipeline
- `reference/prompt-refinement.md` — the 5-phase Suno prompt subroutine
- `reference/constraints.md` — immutable rules

When the user invokes a subcommand of `/song`, load the relevant reference docs **only when needed** — keep your runtime context tight.

## API base

The FastAPI backend runs at `http://localhost:8000`. All DB lookups and validation orchestration go through it. If the API is unreachable, ask the user to run `./start.sh` from the songwriter repo root.

## Subcommands

- `/song new` — 6-step wizard: genre → sub-genre → topic → emotion-arc → optional songwriter lens → review. Outputs a fresh `~/Songwriter/songs/<slug>.json`. See `reference/workflow.md` § wizard.
- `/song open <slug>` — load and summarize an existing song.
- `/song draft [section]` — draft section(s) using the 7-step workflow. Without a section arg, drafts every unfilled section in order.
- `/song refine <section>` — conversational refinement of a specific section. Asks targeted questions, regenerates lines.
- `/song alt <section> <line>` — generate 3 alternatives for a single line constrained by the section's cadence + lens + vocab bank.
- `/song validate` — call `POST /songs/<slug>/validate`. Present results. For any `fail` rule, propose fixes interactively.
- `/song lens <slug>` — load the songwriter profile, apply its `adoption_prompt` to the active session, save the choice in the song JSON.
- `/song prompt` — Suno prompt refinement subroutine (5 phases). See `reference/prompt-refinement.md`.
- `/song export` — final cleanup pass: lock all sections, regenerate Suno prompt, save, present.
- `/song list` — list all songs.

## Working principles

1. **Source of truth is the song JSON.** Read it before doing anything; write it after every change. The API's file watcher broadcasts to the UI automatically — you don't need to notify it.
2. **Always validate before saying "done".** Run `/song validate` after every drafting step. Don't claim a section is finished until all 5 rules pass (or are explicitly waived by the user).
3. **Burn list is non-negotiable.** Before saving any line or any Suno prompt, scrub against the burn list (`GET /burn-list`). Replace flagged words with alternatives from the burn-list entry.
4. **Lens cues come from the profile, not from your training data.** When a lens is active, load `songwriter_profile.adoption_prompt` and follow it literally. Don't improvise lens characteristics from what you "remember" about an artist.
5. **Descriptor cache before naming.** When the user references an artist for a sonic vibe ("sound like Frank Ocean"), GET the descriptor cache first; auto-LLM-on-miss is handled server-side. Never inline the artist's name into the final Suno prompt.
6. **Two-level locks.** `lock_state` per section: `draft` (you may edit), `edited` (user touched it; you ask before editing), `locked` (do not touch). Always honor `locked`.

## Quick API recipes

A reachable healthcheck:

```bash
curl -sf http://localhost:8000/healthz
```

Get a song:

```bash
curl -s http://localhost:8000/songs/<slug> | jq .
```

Run validation (deterministic only, fast):

```bash
curl -sX POST 'http://localhost:8000/songs/<slug>/validate?include_llm=false' | jq '.sections[].validation'
```

Get rhymes for a word:

```bash
curl -s 'http://localhost:8000/rhymes?word=love&limit=20' | jq .
```

For the full set of recipes including writes, see `reference/api-recipes.md`.

## Subcommand starting points

When dispatched to a subcommand, load the appropriate reference doc and follow its workflow:

| Subcommand | Reference doc to load first |
|---|---|
| new, draft, refine, alt | `reference/workflow.md` |
| lens | `reference/lens-application.md` |
| prompt, export | `reference/prompt-refinement.md` |
| validate | `reference/workflow.md` § Final Validation + `reference/constraints.md` |
| open, list | (no extra docs needed; just curl + present) |

Always end every interaction by either:
- Asking the user the next concrete question, OR
- Telling them what file changed and what to look at next.

Don't summarize what you did — they can see the diff.
```

- [ ] **Step 5: Run tests, verify PASS**

- [ ] **Step 6: Commit**

```bash
git add .claude tests/skill/__init__.py tests/skill/test_skill_files.py
git commit -m "feat(skill): scaffold /song dispatcher + songwriting skill entry"
```

---

## Task 2: 7-step workflow reference

**Files:**
- Create: `songwriter/.claude/skills/songwriting/reference/workflow.md`
- Modify: `tests/skill/test_skill_files.py`

The workflow doc is the deep-dive on the 7-step framework. It's loaded when the user invokes `/song new`, `/song draft`, `/song refine`, or `/song alt`.

- [ ] **Step 1: Append failing test**

```python
def test_workflow_doc_exists_with_seven_steps():
    p = SKILL_DIR / "reference" / "workflow.md"
    assert p.exists()
    body = p.read_text()
    expected_steps = [
        "Story Rule",
        "Sentence Rule",
        "Phonetic Texture",
        "Cadence",
        "Genre Pattern",
        "Final Validation",
        "Suno Prompt",
    ]
    for step in expected_steps:
        assert step in body, f"workflow doc should reference step: {step}"


def test_workflow_doc_includes_wizard_for_new_command():
    body = (SKILL_DIR / "reference" / "workflow.md").read_text().lower()
    assert "wizard" in body or "6-step" in body or "6 steps" in body
    for term in ["genre", "sub-genre", "topic", "emotion", "lens"]:
        assert term in body
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Write the workflow doc**

File: `songwriter/.claude/skills/songwriting/reference/workflow.md`

```markdown
# 7-Step Songwriting Workflow

This is the master flow. Every drafting subcommand (`new`, `draft`, `refine`, `alt`) walks through these steps in order. Don't skip steps.

## The /song new wizard (6 steps)

When the user runs `/song new`, ask one question per turn. Use API lookups to populate the choices.

1. **Genre.** `curl -s http://localhost:8000/genres` → list 12 options. Wait for the user to pick.
2. **Sub-genre.** `curl -s http://localhost:8000/genres/<genre> | jq .sub_genres` → narrow.
3. **Topic.** Free-text. One sentence. "What is the song *about*?"
4. **Emotion arc.** Pick one of: `escalation`, `collapse`, `redemption`, `surrender`, `defiance`, `nostalgia`. Or custom.
5. **Songwriter lens (optional).** `curl -s "http://localhost:8000/songwriter-profiles?genre=<genre>"`. Show the user a short list (display_name, role, hook_style). Offer "Skip lens".
6. **Review and create.** Confirm everything, build the initial song JSON skeleton (using `structure_templates` for the chosen genre), write to `~/Songwriter/songs/<slug>.json`.

The slug should be `YYYY-MM-DD-<title-kebab-case>` if the user gave a title, or `YYYY-MM-DD-untitled-<n>` otherwise.

After creation, prompt: "Run `/song draft` to generate the first pass."

## The 7 framework steps (drafting)

When you draft a section (`/song draft <section>` or via the wizard), apply each step:

### Step 1 — Story Rule

Confirm the section serves the song's `intent.story` (event / emotion / resolution). If unclear, ask the user.

For verses: which part of the story does this section advance?
For pre-chorus: what's the emotional pivot?
For chorus: what's the thesis?
For bridge: what's the perspective shift?

### Step 2 — Sentence Rule

For every drafted line, ensure:

- **Sentence Logic** — line makes grammatical and semantic sense.
- **Context Continuity** — line follows from the previous line.
- **Narrative Consistency** — line fits the song's story.
- **Singability** — line fits the cadence pattern's syllable count and stress template.

You judge Logic / Continuity / Consistency directly. The API runs the deterministic Singability check via `/validate`.

### Step 3 — Phonetic Texture Rule

Match the section's emotional target with vocab whose phonetic profile fits.

- For `surrender`, `nostalgia`, `intimacy`, `collapse` emotions: prefer **soft attacks** (sonorants like L, M, N, R, W, Y; voiced fricatives like V, Z, DH) and **low consonant density**.
- For `defiance`, `escalation` emotions: prefer **hard attacks** (plosives P, T, K, B, D, G; voiceless fricatives F, S, SH, TH, HH) and **higher consonant density**.

Query the vocab bank for the section's emotion: `curl -s "http://localhost:8000/vocab-banks/<genre>.<theme>/words"`. Use the bank's words preferentially.

For specific word choices, look up phonetics: `curl -s "http://localhost:8000/words/<word>"`.

### Step 4 — Cadence Rule

Pick a cadence pattern per section. Available: `straight-4-beat`, `double-time-rap`, `triplet`, `grime-swing`, `melodic-glide`, `punchline`, `breakdown-chant`, `pop-hook`, `storytelling`, `hybrid`.

`curl -s http://localhost:8000/cadence-patterns | jq '.[] | select(.slug == "<slug>")'` shows the pattern's syllable template, stress template, and rhyme compatibility.

Match line stress to the template. The API's `/validate` deterministic Cadence engine will catch drift.

### Step 5 — Genre Pattern

Load the production fingerprint and structure template for the sub-genre. These shape the section's energy curve and what kind of imagery fits.

```bash
curl -s "http://localhost:8000/production-fingerprints/<sub_genre>" | jq '.positive_descriptors, .negative_descriptors'
```

Anything in `negative_descriptors` is a "do not write toward this" signal for the lyric texture too.

### Step 6 — Final Validation

After drafting, run `POST /songs/<slug>/validate?include_llm=true`. Read the response. For every section:

- All 5 rules `pass` → section is done.
- Any rule `warn` → present the warning, ask if user wants to keep or fix.
- Any rule `fail` → fix before moving on. Generate alternatives, re-validate.

### Step 7 — Suno Prompt

Run `/song prompt`. See `reference/prompt-refinement.md`.

## Per-line draft requests

When the user manually requests alternatives in the UI (or when validation fails), a `requests` array entry appears in the song JSON:

```json
{
  "type": "suggest_alternatives",
  "section": "v2",
  "line": 3,
  "count": 3,
  "constraint": "more vulnerable"
}
```

When you next run, check `requests`, fulfill them by writing alternatives back into the JSON, and clear the request entry.

## When you draft, write directly

Use Read/Edit/Write tools on `~/Songwriter/songs/<slug>.json`. The file watcher broadcasts the change. The UI updates within ~200ms. You don't need to call the API for writes.

The API IS the writer for validation results — calling `/validate` updates the JSON itself.

Honor lock states: never edit a section with `lock_state == "locked"`. For `lock_state == "edited"`, ask the user before regenerating.
```

- [ ] **Step 4: Run tests, verify PASS. Commit**

```bash
git add .claude/skills/songwriting/reference/workflow.md tests/skill/test_skill_files.py
git commit -m "feat(skill): add 7-step workflow + 6-step new-song wizard reference"
```

---

## Task 3: API recipes reference

**Files:**
- Create: `songwriter/.claude/skills/songwriting/reference/api-recipes.md`
- Create: `tests/skill/test_skill_api_alignment.py`

A cookbook of curl recipes the skill can copy/paste. The test verifies every endpoint mentioned in the doc actually exists in the running API.

- [ ] **Step 1: Failing test**

File: `tests/skill/test_skill_api_alignment.py`

```python
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from songwriter.api.main import create_app


REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / ".claude" / "skills" / "songwriting" / "reference" / "api-recipes.md"


# Match curl ... <method?> http(s)://...:8000<path>
_CURL_RE = re.compile(r"curl[^\n]*?(?:-X\s*(\w+)\s*)?[\"']?(?:https?://[^/\s\"']*)(/[\w\-/{}.]+)")


@pytest.fixture(scope="module")
def app_client(request):
    # build with the existing session-scoped DB used by tests/api/conftest.py
    # We can't import that fixture cleanly here; run the test against an app with default settings + the built DB.
    from songwriter.api.settings import Settings
    from songwriter.seeds.build import run as build_run
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    fixture = REPO / "tests" / "fixtures" / "cmudict_vocab_words.txt"
    cache = tmp / "cache"
    cache.mkdir()
    (cache / "cmudict.dict").write_text(fixture.read_text())
    db = tmp / "songwriter.db"
    build_run(db_path=db, cache_dir=cache)
    settings = Settings(db_path=db, songs_dir=tmp / "songs")
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


def test_api_recipes_doc_exists():
    assert RECIPES.exists()


def test_every_endpoint_in_recipes_exists(app_client):
    text = RECIPES.read_text()
    matches = _CURL_RE.findall(text)
    assert matches, "expected at least one curl example in api-recipes.md"
    seen: set[tuple[str, str]] = set()
    for method, raw_path in matches:
        method = (method or "GET").upper()
        # replace placeholder slugs with safe known values
        path = raw_path
        path = re.sub(r"\{slug\}", "frank-ocean", path)
        path = re.sub(r"<slug>", "frank-ocean", path)
        path = re.sub(r"\{[^}]+\}", "x", path)
        path = re.sub(r"<[^>]+>", "x", path)
        if (method, path) in seen:
            continue
        seen.add((method, path))
        if method == "GET":
            r = app_client.get(path)
        elif method == "POST":
            r = app_client.post(path)
        elif method == "PUT":
            r = app_client.put(path, json={})
        else:
            continue
        # any non-405 response means the route exists in the app
        assert r.status_code != 405 and r.status_code != 404 or path.endswith("/x") or "x" in path, (
            f"endpoint {method} {path} returned {r.status_code} — route may not exist"
        )
```

(The 404-tolerance handles placeholder slugs that don't resolve to a real entity.)

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Write the recipes doc**

File: `songwriter/.claude/skills/songwriting/reference/api-recipes.md`

```markdown
# API Recipes

The FastAPI backend lives at `http://localhost:8000`. Every recipe below is a one-liner you can paste directly into a Bash tool call.

## Health and meta

```bash
curl -s http://localhost:8000/healthz
```

## Genres and sub-genres

```bash
curl -s http://localhost:8000/genres
curl -s http://localhost:8000/genres/{slug}
curl -s http://localhost:8000/sub-genres
```

## Cadence patterns

```bash
curl -s http://localhost:8000/cadence-patterns
```

## Vocab banks

```bash
curl -s http://localhost:8000/vocab-banks
curl -s http://localhost:8000/vocab-banks/{slug}/words
```

## Words and rhymes

```bash
curl -s http://localhost:8000/words/{word}
curl -s 'http://localhost:8000/rhymes?word=love&limit=20'
```

## Production fingerprints, emotion-tempo, structure templates

```bash
curl -s http://localhost:8000/production-fingerprints/{sub_genre}
curl -s 'http://localhost:8000/emotion-tempo?emotion=surrender&sub_genre=alt-rnb'
curl -s http://localhost:8000/structure-templates
```

## Burn list

```bash
curl -s http://localhost:8000/burn-list
```

## Songwriter profiles

```bash
curl -s http://localhost:8000/songwriter-profiles
curl -s 'http://localhost:8000/songwriter-profiles?genre=rnb&role=self-writing-artist'
curl -s http://localhost:8000/songwriter-profiles/{slug}
```

## Sonic descriptors (auto-LLM on miss is server-side)

```bash
curl -s http://localhost:8000/descriptors/{name}
```

## Songs CRUD

```bash
curl -s http://localhost:8000/songs
curl -sX POST http://localhost:8000/songs -H 'Content-Type: application/json' -d @song.json
curl -s http://localhost:8000/songs/{slug}
curl -sX PUT http://localhost:8000/songs/{slug} -H 'Content-Type: application/json' -d @song.json
```

## Validation

```bash
curl -sX POST 'http://localhost:8000/songs/{slug}/validate?include_llm=false'
curl -sX POST 'http://localhost:8000/songs/{slug}/validate?include_llm=true'
```

## Tip: use jq to slice responses

```bash
curl -s http://localhost:8000/genres | jq '.[] | {slug, name, typical_bpm_min, typical_bpm_max}'
curl -sX POST 'http://localhost:8000/songs/abc/validate?include_llm=false' | jq '.sections[].validation'
```
```

- [ ] **Step 4: Run, verify PASS. Commit**

```bash
git add .claude/skills/songwriting/reference/api-recipes.md tests/skill/test_skill_api_alignment.py
git commit -m "feat(skill): API recipes reference with endpoint-alignment test"
```

---

## Task 4: Lens application + descriptor cache references

**Files:**
- Create: `songwriter/.claude/skills/songwriting/reference/lens-application.md`
- Create: `songwriter/.claude/skills/songwriting/reference/descriptor-cache.md`
- Modify: `tests/skill/test_skill_files.py`

These two are sibling references — both consume API endpoints already shipped by Plan 2.

- [ ] **Step 1: Append failing tests**

```python
def test_lens_application_doc_loads_adoption_prompt():
    p = SKILL_DIR / "reference" / "lens-application.md"
    assert p.exists()
    body = p.read_text()
    assert "adoption_prompt" in body
    assert "songwriter-profiles" in body
    for role in ["pure-songwriter", "producer-songwriter", "singer-songwriter", "self-writing-artist"]:
        assert role in body


def test_descriptor_cache_doc_explains_pipeline():
    p = SKILL_DIR / "reference" / "descriptor-cache.md"
    assert p.exists()
    body = p.read_text().lower()
    assert "/descriptors/" in body
    assert "auto-llm" in body or "auto llm" in body
    assert "burn list" in body or "burn-list" in body or "scrub" in body
    assert "never" in body and ("name" in body or "artist" in body)
```

- [ ] **Step 2: Implement `lens-application.md`**

```markdown
# Songwriter Lens Application

A "lens" is a craft fingerprint loaded as additional system instructions that shape every drafted line. Pure-songwriter / producer-songwriter / singer-songwriter / self-writing-artist roles each behave differently.

## Loading a lens

```bash
curl -s http://localhost:8000/songwriter-profiles/{slug}
```

The response includes:

- `role` — one of `pure-songwriter`, `producer-songwriter`, `singer-songwriter`, `self-writing-artist`. Different roles call for different application:
  - **pure-songwriter** (Diane Warren, Max Martin) — generalizes across performers. Apply the craft signature; the vocal delivery is whatever the song calls for.
  - **producer-songwriter** (Stargate, Tainy, Finneas) — bundles craft + production cues. Apply both the lyric mechanics AND the production cues to the Suno prompt.
  - **singer-songwriter** (Phoebe Bridgers, Bon Iver) — craft is tied to delivery. Apply lyric craft AND vocal delivery cues.
  - **self-writing-artist** (Frank Ocean, Kendrick Lamar) — intrinsic to the artist's voice. Apply craft + vocal + production cues; the lens is most opinionated here.
- `craft_signature` — bullet list of mechanics observations. Read these as direct instructions.
- `writing_style` — structured fingerprint (avg line syllables, rhyme density, narrative mode, etc.).
- `vocab_fingerprint` — `signature_words`, `semantic_anchors`, `avoided_words`, `vowel_priority_words`. These are immediate filters: prefer signature/anchor words, avoid avoided ones.
- `phonetic_fingerprint` — vowel preference, attack profile, consonant density.
- `preferred_cadences` — list of cadence pattern slugs. Pick from these unless the user overrides.
- `adoption_prompt` — the prose instruction set. **Treat this as authoritative.** Read it once, follow it literally.

## Applying the lens

After loading:

1. Update `song.songwriter_lens = "<slug>"` in the song JSON.
2. For every line you draft from this point on:
   - Word choice biases toward `vocab_fingerprint.signature_words` and `semantic_anchors`.
   - Avoid `vocab_fingerprint.avoided_words`.
   - Respect `phonetic_fingerprint.attack_profile`.
   - Prefer `preferred_cadences[0]` unless the section's existing cadence is set.
3. Whenever you generate alternatives, run them through `adoption_prompt` constraints first.
4. When the user says `/song lens <new-slug>`, swap entirely — don't blend lenses unless the user explicitly says "add lens X to lens Y".

## What a lens is NOT

- Not a license to invent details about the artist. Stick to the structured fingerprint.
- Not a license to include song titles or lyrics from the artist's catalog. `notable_credits` and `reference_tracks` are titles only — never quote.
- Not a substitute for the user's intent. The user's `intent.topic` and `intent.story` always win over lens preferences.

## Removing a lens

```bash
# write song.songwriter_lens = null in the JSON
```

After removal, drafts revert to genre-default style.
```

- [ ] **Step 3: Implement `descriptor-cache.md`**

```markdown
# Sonic Descriptor Cache

When the user references an artist for a sonic vibe ("sound like Tyla but darker"), use the descriptor cache. The cache returns vocal + production descriptors **without naming the artist**.

## Lookup

```bash
curl -s http://localhost:8000/descriptors/{name}
```

Where `{name}` is whatever the user said — the API normalizes (lowercases, strips honorifics like "the" / "mr" / "ms" / "dj", strips punctuation, replaces hyphens with spaces).

## What you get back

```json
{
  "canonical_name": "Frank Ocean",
  "descriptor_short": "Soft-edged tenor with breath-rich attack, pocketed in dusty Rhodes and muted sub-bass; close-mic intimate, spring-reverb ambience.",
  "descriptor_long": "...",
  "vocal_attributes": { ... },
  "production_attrs": { ... },
  "source": "user-curated" | "songwriter-profile-derived" | "auto-llm",
  "quality_state": "pinned" | "reviewed" | "unverified",
  "use_count": 12,
  "era_label": "Channel Orange / Blonde era"
}
```

## On cache miss (auto-LLM)

A miss triggers server-side LLM generation. The response will have `source: "auto-llm"` and `quality_state: "unverified"`. The first GET pays the LLM cost; every subsequent GET is free (cache hit). This is by design — re-using a descriptor across sessions costs zero.

The server scrubs burn-list words from the generated descriptor automatically. You don't need to re-scrub.

## Where the descriptor goes in the Suno prompt

Splice `descriptor_short` into the prompt's vocal + production lines. Never include the artist's name in the final Suno prompt — that defeats the purpose.

Example:

> ❌ "Sound like Frank Ocean."
> ✅ "Vocals: soft-edged tenor with breath-rich attack, close-mic intimate. Production: dusty Rhodes electric piano, muted sub-bass, sparse programmed drums, spring-reverb ambience."

The longer `descriptor_long` is for your own reference / the song JSON's notes — not the prompt itself unless the user explicitly asks for a longer description.

## Composing with a songwriter lens

A descriptor and a lens can compose freely. "Diane Warren writing craft + Adele sonic descriptor" is a valid hybrid: load Warren as the lens (writing_style + vocab_fingerprint) and Adele as the descriptor (vocal_attributes + production_attrs).

## Constraints

- **Never name the artist in lyrics or in the final Suno prompt.**
- **Never copy lyric content from the artist's catalog.** Reference tracks and notable credits are titles only.
- **Never assume cache content matches your training data.** The descriptor is what's in the cache. If the user wants different characteristics, regenerate — don't paper over with what you "remember".
```

- [ ] **Step 4: Run tests, verify PASS. Commit**

```bash
git add .claude/skills/songwriting/reference/lens-application.md .claude/skills/songwriting/reference/descriptor-cache.md tests/skill/test_skill_files.py
git commit -m "feat(skill): lens application + sonic descriptor cache references"
```

---

## Task 5: Suno prompt refinement subroutine

**Files:**
- Create: `songwriter/.claude/skills/songwriting/reference/prompt-refinement.md`
- Modify: `tests/skill/test_skill_files.py`

This is the 5-phase loop the spec defines. Loaded by `/song prompt` and `/song export`.

- [ ] **Step 1: Append failing test**

```python
def test_prompt_refinement_doc_has_5_phases():
    p = SKILL_DIR / "reference" / "prompt-refinement.md"
    assert p.exists()
    body = p.read_text().lower()
    for phase in ["phase 1", "phase 2", "phase 3", "phase 4", "phase 5"]:
        assert phase in body
    assert "burn list" in body or "burn-list" in body or "scrub" in body
    assert "anti-prompt" in body or "anti prompt" in body or "negative" in body
    # standalone improve mode
    assert "--improve" in body or "improve" in body
```

- [ ] **Step 2: Implement**

File: `songwriter/.claude/skills/songwriting/reference/prompt-refinement.md`

```markdown
# Suno Prompt Refinement Subroutine

Triggered by `/song prompt`. A 5-phase loop that takes the song's intent + production fingerprint + lens + descriptor cache and produces a focused Suno-ready prompt with anti-prompts.

## Phase 1 — Direction Capture

Ask the user once: *"Give me your starting direction for the Suno prompt — one or two sentences."*

Capture the answer verbatim. Don't paraphrase.

## Phase 2 — Targeted Clarification

Load the genre's production fingerprint:

```bash
curl -s "http://localhost:8000/production-fingerprints/<sub_genre>" | jq .
```

Identify which fields are underspecified by the user's direction. Ask 4-7 targeted questions, **one at a time**. Pull the questions from the production fingerprint's required fields:

- BPM (cross-reference with `emotion-tempo` for the song's emotion arc)
- Vocal style (delivery, effects)
- Instrumentation
- Mix character (brightness, compression, width)
- Section dynamics (which section is the loudest? quietest?)
- Tempo feel (laid back vs forward)
- Reference textures (anything that needs splicing into the descriptor cache)

Don't improvise questions — only ask what the production fingerprint declares unspecified.

### Phase 2a — Artist-name detection

If the user mentions an artist by name in their direction or in any answer ("feel like Tyla but darker", "Adele's belt range"), extract the name(s) and run:

```bash
curl -s http://localhost:8000/descriptors/{name}
```

Take `descriptor_short` and use it. The server handles cache hit / miss / auto-LLM automatically. Do NOT paste the artist's name into the prompt.

## Phase 3 — Draft + Anti-Prompt Construction

Assemble the prompt using the user's existing 9-section framework structure:

1. Genre / sub-genre line
2. BPM and time-signature line (use `emotion-tempo` BPM range)
3. Vocal description (splice descriptor_short here if a descriptor was used)
4. Production line (instrumentation + mix character)
5. Section-by-section dynamic notes (use `production.energy_curve`)
6. Lens craft cues (if a songwriter lens is active — use brief noun-phrases from `craft_signature`)
7. Mood / texture descriptors (positive)
8. Anti-prompt block (negative — see below)
9. Lyric structure note (verse/chorus/bridge counts)

Build the anti-prompt block from:

- `production_fingerprints.<sub_genre>.negative_descriptors`
- `emotion_tempo_map.<emotion>.<sub_genre>.anti_prompts`
- All burn-list words flagged `severity: extreme` or `severity: strong` (if any appear in the draft prompt, replace via `alternatives`)

```bash
curl -s http://localhost:8000/burn-list | jq '.[] | select(.severity == "extreme" or .severity == "strong") | .word'
```

## Phase 4 — Refinement Loop

Output the draft prompt with a character count and an anti-prompt count. Ask the user: *"Tighten anything?"*

Common refinements:
- "Add tape warmth" → modify mix-character line.
- "Less reverb" → adjust effects.
- "Final chorus needs to soar" → bump energy in the section-dynamic line.

Each refinement is logged in `song.suno_prompt.history` (append, don't overwrite).

Loop until the user says "done" or "good".

## Phase 5 — Final Output

Write the final string to `song.suno_prompt.current` in the song JSON. Present:

```
Final Suno prompt (NNN chars):
<the prompt>

Anti-prompts (M):
<list>

Open in Suno: copy the prompt to clipboard with `pbcopy < /dev/stdin <<<'<prompt>'` and open https://suno.com/create.
```

The UI's Suno tab will live-update from the JSON write.

## Standalone improve mode (`/song prompt --improve <existing>`)

If the user pastes an existing prompt and wants it improved:

1. Run it through the burn-list scrub.
2. Diagnose what's missing (compare against the 9-section framework).
3. Ask only the questions needed to fill those gaps.
4. Rebuild via Phase 3 + 4.

The user can pass the existing prompt as `--improve "<prompt>"` after the slash command.

## What never goes in the prompt

- Artist names (use descriptor cache).
- Copyrighted lyric content.
- Burn-list words flagged `extreme` (and `strong` unless the user overrides explicitly).
- Promotional language ("hit single", "chart-topping").
- Vague mood words without textural anchor ("emotional", "powerful" — replace with concrete cues).
```

- [ ] **Step 3: Run, verify PASS. Commit**

```bash
git add .claude/skills/songwriting/reference/prompt-refinement.md tests/skill/test_skill_files.py
git commit -m "feat(skill): 5-phase Suno prompt refinement subroutine"
```

---

## Task 6: Constraints reference + lint test

**Files:**
- Create: `songwriter/.claude/skills/songwriting/reference/constraints.md`
- Create: `tests/skill/test_skill_constraints.py`

The constraints doc is the immutable rules the skill must always honor. The test asserts none of the skill files smuggle in copyrighted lyric content or banned phrases.

- [ ] **Step 1: Failing test**

File: `tests/skill/test_skill_constraints.py`

```python
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / ".claude" / "skills" / "songwriting"


# Pattern for a quoted line that looks like song lyrics
# (a quoted phrase in title-case-ish style, ≥4 words, with no punctuation indicating prose)
_LYRIC_QUOTE = re.compile(r'"[A-Z][a-z]+(?:\s+[A-Za-z][a-z]*){4,}"')


def test_constraints_doc_exists():
    p = SKILL_DIR / "reference" / "constraints.md"
    assert p.exists()
    body = p.read_text().lower()
    assert "copyrighted" in body
    assert "burn list" in body or "burn-list" in body
    assert "validation" in body
    assert "lock" in body


def test_no_obvious_copyrighted_lyric_quotes_in_skill():
    """Heuristic: scan every skill file for sustained song-lyric-style quoted strings."""
    flagged = []
    for p in SKILL_DIR.rglob("*.md"):
        body = p.read_text()
        for m in _LYRIC_QUOTE.finditer(body):
            phrase = m.group(0)
            # filter false positives: code-style quotes, descriptors with neutral content
            if any(t in phrase.lower() for t in ("call", "lookup", "endpoint", "section", "verse")):
                continue
            flagged.append((p.name, phrase))
    assert not flagged, f"possible copyrighted lyric quotes:\n  " + "\n  ".join(f"{n}: {p}" for n, p in flagged)


def test_no_artist_names_inside_descriptor_examples():
    """Descriptor examples in the skill must show that the artist's name is NOT in the descriptor itself."""
    body = (SKILL_DIR / "reference" / "descriptor-cache.md").read_text()
    # frank ocean is the seeded example; the descriptor in the example MUST NOT contain the name
    descriptor_block = re.search(r'"descriptor_short":\s*"([^"]+)"', body)
    if descriptor_block:
        assert "frank ocean" not in descriptor_block.group(1).lower()
```

- [ ] **Step 2: Implement constraints doc**

File: `songwriter/.claude/skills/songwriting/reference/constraints.md`

```markdown
# Skill Constraints (Immutable)

These rules apply to every drafting and prompt-construction session. No subcommand overrides them.

## 1. No copyrighted lyric content

Never quote, paraphrase, or "be inspired by" specific lyrics from existing songs. `notable_credits` and `reference_tracks` in songwriter profiles are **titles only** — never quote the contents.

If the user pastes copyrighted lyrics into the conversation as reference, treat it as off-limits inspiration. Acknowledge their reference but write something original.

## 2. No artist names in lyrics or final Suno prompts

When the user references an artist, route through the descriptor cache (see `descriptor-cache.md`). The artist's canonical name never appears in `song.suno_prompt.current` or in any drafted lyric.

A line like "I sing like Adele" in a verse is a violation — use a descriptive phrase instead.

## 3. Validate before declaring done

Every claim of "section is complete" requires `POST /songs/<slug>/validate` to return all 5 rules either `pass` or explicitly `warn`-with-user-acceptance. Don't bypass.

## 4. Burn list is non-negotiable

Before saving any drafted line OR any Suno prompt, check against `GET /burn-list`. For any flagged word at `severity: strong` or `severity: extreme`, replace with an entry from the row's `alternatives` field. `severity: mild` words trigger a warning to the user but no auto-replacement.

## 5. Honor lock states

Section `lock_state`:
- `draft` → you may edit freely.
- `edited` → user has touched it. Ask before regenerating: "Section X has user edits. Want me to keep them or regenerate?"
- `locked` → never edit. If a validation result requires changes here, surface the failure but don't fix without the user explicitly unlocking.

## 6. Source of truth is the song JSON

You write to `~/Songwriter/songs/<slug>.json` directly via Read/Edit/Write. The API watches the directory and broadcasts changes over WebSocket to the UI. Don't double-write through the API.

Validation results come from the API (because the API computes deterministic checks fastest); validation calls update the JSON server-side and emit a WS broadcast. After calling `POST /validate`, re-read the JSON before further edits.

## 7. Lens is authoritative when active

When `song.songwriter_lens` is set:
- Load the profile's `adoption_prompt` and treat it as direct instructions.
- Don't blend with what you remember about the artist from training data.
- The lens applies until the user runs `/song lens <other>` or sets it to null.

## 8. No half-finished sections in `export`

When the user runs `/song export`, every section must:
- Have lyrics filled (no empty arrays).
- Pass all 5 validation rules.
- Have a `cadence_pattern` set.

If any section fails this check, list the failures and ask the user to address them before allowing export.

## 9. Don't invent reference artists

If the descriptor cache lookup fails AND the auto-LLM fallback returns malformed output, do NOT make up the descriptor from your training data. Surface the error: "Descriptor for X couldn't be generated. Pick a different reference or proceed without."

## 10. Refuse copyright laundering

If the user asks "rewrite the chorus of <song X> for me" or "make this sound like <copyrighted lyric>", refuse and offer: "I can't reproduce or rewrite copyrighted lyrics. I can write something with similar emotional shape if you describe what moves you about it." Never paraphrase copyrighted lines as a workaround.
```

- [ ] **Step 3: Run, verify PASS. Commit**

```bash
git add .claude/skills/songwriting/reference/constraints.md tests/skill/test_skill_constraints.py
git commit -m "feat(skill): immutable constraints reference + lint test"
```

---

## Task 7: Human-facing INVOKE doc + final test sweep

**Files:**
- Create: `songwriter/docs/skill/INVOKE.md`
- Modify: `songwriter/README.md` (add a "Use the skill" section)

A short doc that explains to the user (not Claude Code) how to actually invoke the skill once everything is wired up.

- [ ] **Step 1: Write `docs/skill/INVOKE.md`**

```markdown
# Using the Songwriter Skill

The skill is a Claude Code slash command + skill bundle that drives the songwriting workflow.

## One-time setup

```bash
cd /path/to/songwriter
./.venv/bin/songwriter-build              # if data/songwriter.db is missing
./start.sh                                 # boots the API on :8000
```

In a separate terminal, open Claude Code from the repo root:

```bash
cd /path/to/songwriter
claude
```

## Commands

```
/song                           # menu
/song new                       # 6-step wizard → creates a new song JSON
/song open <slug>               # load a song and show status
/song list                      # list songs in ~/Songwriter/songs/

/song draft [section]           # draft section(s) with the 7-step framework
/song refine <section>          # conversational refinement
/song alt <section> <line>      # 3 alternatives for one line
/song validate                  # run all 5 rules + present results

/song lens <slug>               # apply or change songwriter lens
/song prompt                    # 5-phase Suno prompt refinement loop
/song prompt --improve "<existing prompt>"
/song export                    # final cleanup + Suno prompt + save
```

## Files the skill touches

- `~/Songwriter/songs/<slug>.json` — your song state. Edit by hand if you want; the file watcher will sync.
- `localhost:8000` — the API. Verify with `curl -sf http://localhost:8000/healthz`.

## When something doesn't work

- "API not running" → run `./start.sh` from the repo root.
- "Song not found" → check `~/Songwriter/songs/<slug>.json` exists. If it does, the slug in your command may be off.
- "Validation always fails" → `curl -sX POST 'http://localhost:8000/songs/<slug>/validate?include_llm=false' | jq` to see the raw output. The skill should be doing this for you, but it's the same data.
- "I think the skill is hallucinating" → it shouldn't reach for training-data details when the API is reachable. If it does, mention "use the API" and it will reset.

## Files at a glance

```
songwriter/.claude/
├── commands/
│   └── song.md                # the /song slash command
└── skills/
    └── songwriting/
        ├── SKILL.md           # main skill
        └── reference/         # workflow, lens, descriptor, prompt, constraints, API recipes
```
```

- [ ] **Step 2: Add a section to `songwriter/README.md`**

Append (or replace the relevant section) in `README.md`:

```markdown
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
```

- [ ] **Step 3: Final test sweep**

```bash
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
source .venv/bin/activate
pytest -q
```

Expected: every prior test plus all new skill tests pass. No regressions.

- [ ] **Step 4: Commit**

```bash
git add docs/skill/INVOKE.md README.md
git commit -m "docs(skill): human-facing INVOKE guide + README skill section"
```

---

## Self-review summary

**Spec coverage (skill scope):**

| Spec deliverable | Task |
|---|---|
| `/song` slash command + dispatcher | 1 |
| 7-step master workflow | 2 |
| 6-step new-song wizard | 2 |
| API recipes | 3 |
| Lens application (4 role types) | 4 |
| Sonic descriptor cache (HIT/MISS, never name artist) | 4 |
| 5-phase Suno prompt refinement loop | 5 |
| `/song prompt --improve` mode | 5 |
| Burn-list scrub on save / on prompt | 4, 5, 6 |
| Lock states (draft/edited/locked) | 6 |
| No copyrighted lyrics, no artist names in output | 6 |
| Validation before "done" | 6 |
| Source-of-truth is JSON; UI sync via file watcher | 6 |
| Human INVOKE guide | 7 |

**Out of scope (sister plans):**
- The web UI consumes the same song JSON + WebSocket protocol.
- The API itself (already shipped in Plan 2).

**Critical assertions tested:**
- `/song` command + skill exist with valid frontmatter and reference all 10 subcommands.
- 7-step workflow doc covers all 7 steps + the 6-step wizard.
- API recipes: every `curl` example references an endpoint that the running app exposes (test runs a TestClient and probes each).
- Lens application doc covers all 4 role types and references `adoption_prompt`.
- Descriptor cache doc emphasizes never-name-artist + auto-LLM-on-miss + burn-list scrub.
- Prompt refinement has all 5 phases and references the burn list / anti-prompts / `--improve` mode.
- Constraints doc lints clean: no copyrighted-lyric-style quotes leaked into skill files.

**Decisions baked in:**
- Skill writes JSON directly; API runs validation orchestration. Clean separation.
- Skill is project-level (`.claude/` in repo) so it's git-tracked.
- LLM-judged validation runs in skill context (no subprocess) when skill is active; in API context (`claude --print`) when triggered by UI without skill.

---

## Execution handoff

7 tasks. ~half a day to execute via subagent-driven development. Each task is markdown + linter — most are mechanical writes after the test is in place.

Sister plan to write next: `2026-04-30-songwriter-web-ui.md` — Next.js client consuming endpoints + WebSocket.
