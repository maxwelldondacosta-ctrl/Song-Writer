#!/usr/bin/env python3
"""Autonomous improvement brainstormer for the Songwriter app.

Reads the current codebase, rotates through focus areas, calls Claude Sonnet,
and appends 3-5 concrete improvement ideas to docs/brainstorm-log.md.

Designed to run headlessly via launchd every 20 minutes.
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

REPO_DIR  = pathlib.Path("/Users/mdacosta/Desktop/Song Writing/songwriter")
LOG_FILE  = REPO_DIR / "docs" / "brainstorm-log.md"
GEMINI_KEY_FILE = pathlib.Path.home() / ".gemini_api_key"
GEMINI_MODEL    = "gemini-2.5-flash"
MAX_TOKENS      = 1800

FOCUS_AREAS = [
    ("A", "Lyric Quality",     "prompt design, craft rules, section-by-section generation, story engines, rhyme quality"),
    ("B", "UX & Workflow",     "song creation flow, editing, what the user sees, section locking, regenerate single section"),
    ("C", "Genre & Music Theory", "cadence patterns, chord progressions, new genres, anchor vocab, sub-genre differentiation"),
    ("D", "Cost & Speed",      "token efficiency, parallel calls, smarter repair targeting, caching, streaming"),
    ("E", "Suno Integration",  "style prompts, instrumentation tags, BPM/key metadata, arrangement hints, Suno-specific burn list"),
    ("F", "Wild Card",         "anything surprising — new features, integrations, structural changes, things that don't fit above"),
]

# Files to read for context (relative to REPO_DIR)
CONTEXT_FILES = [
    "src/songwriter/api/routes/draft.py",
    "src/songwriter/api/llm.py",
    "src/songwriter/api/validation/orchestrator.py",
    "src/songwriter/api/routes/draft_defaults.py",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_key() -> str:
    if GEMINI_KEY_FILE.exists():
        return GEMINI_KEY_FILE.read_text().strip()
    return os.environ.get("GEMINI_API_KEY", "")


def read_file_safe(path: pathlib.Path, max_chars: int = 4000) -> str:
    try:
        text = path.read_text(errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + f"\n... [truncated at {max_chars} chars]"
        return text
    except Exception as e:
        return f"[could not read: {e}]"


def read_recent_songs(n: int = 2) -> str:
    songs_dir = pathlib.Path.home() / "Songwriter" / "songs"
    if not songs_dir.exists():
        return "[no songs directory]"
    files = sorted(songs_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:n]
    parts = []
    for f in files:
        try:
            d = json.loads(f.read_text())
            sections = d.get("sections", [])
            sample = []
            for s in sections[:2]:
                lyrics = s.get("lyrics") or []
                if lyrics:
                    sample.append(f"  [{s['label']}] {lyrics[0]!r}")
            parts.append(
                f"Song: {d.get('title')} | {d.get('genre')}/{d.get('sub_genre')}\n"
                + "\n".join(sample)
            )
        except Exception:
            pass
    return "\n\n".join(parts) or "[no recent songs]"


def pick_focus(log_text: str) -> tuple[str, str, str]:
    """Pick the focus area least recently used based on the log."""
    counts = {letter: 0 for letter, _, _ in FOCUS_AREAS}
    for letter, _, _ in FOCUS_AREAS:
        counts[letter] = log_text.count(f"Focus: {letter}.")
    # Pick the one with fewest appearances (break ties by order)
    letter = min(counts, key=lambda k: counts[k])
    for l, name, desc in FOCUS_AREAS:
        if l == letter:
            return l, name, desc
    return FOCUS_AREAS[0]


def read_log_tail(max_chars: int = 3000) -> str:
    if not LOG_FILE.exists():
        return "(no previous sessions)"
    text = LOG_FILE.read_text()
    return text[-max_chars:] if len(text) > max_chars else text


def call_gemini(prompt: str, key: str) -> str:
    system = (
        "You are an expert software engineer and product designer brainstorming "
        "improvements for a songwriter app. Be specific, concrete, and opinionated. "
        "Read the code carefully before generating ideas. Every idea must reference "
        "actual file names, function names, or code patterns you observed."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": MAX_TOKENS, "temperature": 0.9},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode())
    candidates = raw.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {raw}")
    parts = candidates[0].get("content", {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def append_to_log(session_text: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        LOG_FILE.write_text("# Songwriter — Improvement Brainstorm Log\n\nIdeas generated autonomously every 20 minutes.\nReview with the user to decide what to build next.\n\n")
    with LOG_FILE.open("a") as f:
        f.write(session_text + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    key = read_key()
    if not key:
        print("ERROR: no Anthropic key found", file=sys.stderr)
        sys.exit(1)

    log_tail    = read_log_tail()
    focus_l, focus_name, focus_desc = pick_focus(log_tail)
    timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build context block from source files
    context_parts = []
    for rel in CONTEXT_FILES:
        path = REPO_DIR / rel
        context_parts.append(f"=== {rel} ===\n{read_file_safe(path)}")
    context_block = "\n\n".join(context_parts)

    recent_songs = read_recent_songs()

    prompt = f"""You are brainstorming improvements for the Songwriter app.

## Current codebase context

{context_block}

## Recent song output samples (to judge quality)

{recent_songs}

## What's been covered in recent brainstorm sessions

{log_tail}

---

## Your task

Focus area for THIS session: **{focus_l}. {focus_name}** — {focus_desc}

Generate exactly 3-5 concrete improvement ideas within this focus area.
Reference actual code you read above (file names, function names, specific lines).
Do NOT repeat ideas that appear in the recent sessions above.

Format your response as a markdown block starting with:

---
## [{timestamp}] Session — Focus: {focus_l}. {focus_name}

### 1. [Short punchy title]
**Problem:** [what's currently wrong or missing — quote code if relevant]
**Idea:** [what to build or change, concretely]
**How:** [implementation sketch: which file, which function, what changes]
**Effort:** S / M / L
**Impact:** [why this matters to the user]

[repeat ### 2, ### 3, etc.]

---

Output ONLY the markdown block above. No preamble, no sign-off."""

    try:
        response = call_gemini(prompt, key)
        # Ensure it starts with the separator
        if not response.strip().startswith("---"):
            response = "---\n" + response
        if not response.strip().endswith("---"):
            response = response.rstrip() + "\n---"
        append_to_log("\n" + response + "\n")
        print(f"[brainstorm] {timestamp} — appended Focus {focus_l} session to {LOG_FILE}")
    except Exception as e:
        error_block = (
            f"\n---\n## [{timestamp}] Session — ERROR\n\n"
            f"Agent failed: {e}\n\n---\n"
        )
        append_to_log(error_block)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
