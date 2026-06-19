# Songwriter App — Design Spec

**Date:** 2026-04-30
**Status:** Approved by user, ready for implementation plan
**Author:** brainstormed collaboratively in Claude Code session

## Problem

The user has 13 hand-authored songwriting framework documents (Story Rule, Sentence Rule, Phonetic Texture Rule, Cadence Rule, Rhyme-Cadence Interaction Guide, plus genre pattern libraries for Deathcore, Pop, R&B, and a Rap Artist Mode Matrix, plus a Suno prompt framework). The framework is solid but lives as 13 separate `.txt` files. Songs generated through Suno using ad-hoc prompts produce three failure modes the user explicitly named:

1. **Lyrics that make no sense and have no soul** — generic emotion words ("feel the pain, broken heart"), no story, no specificity.
2. **Songs that sound the same as every other AI song** — same vocab cliches, token-bias drift toward synthwave/moody-cinematic, identical-sounding default vocals.
3. **Intent-output mismatch** — asking for a slow love ballad and getting an upbeat pop song; asking for one genre and getting a different one.

The framework as documents is not enough to fix these problems at scale. It needs to become a queryable, deeply-encoded system that operationalizes the rules and constrains every drafted lyric and every Suno prompt.

## Goals

- Build a Claude Code-native songwriting app that operationalizes the user's existing 5-rule framework + 10-pattern cadence library + 12-genre coverage (existing 4 + 8 more) at sub-genre depth.
- Encode phonetic / sonic data deeply enough to support real elocution-aware lyric writing — vowel shapes, consonant attack profiles, syllable stress, rhyme classes — across English, Spanish, and West African languages relevant to ship genres.
- Build first-class **songwriter profiles** (not just artist profiles) — pure songwriters, producer-songwriters, singer-songwriters, and self-writing artists each with structured craft fingerprints used as a writing lens during drafting.
- Build a **sonic descriptor cache** that translates user references like "sound like Frank Ocean" into non-naming descriptors (vocal timbre, production signature, tempo zone, mix character) cached for zero-LLM-cost on subsequent uses.
- Build a conversational **Suno prompt refinement loop** that takes user direction, asks targeted clarifying questions to fill in production fingerprint gaps, scrubs the prompt against a token-bias burn list, and outputs a focused Suno-ready prompt with anti-prompts.
- Ship a polished local web UI (looks like a real product, not a hacky dashboard) that pairs with the Claude Code skill — the UI handles visual editing, vocab browsing, and song state visualization without making any LLM calls; the skill handles all AI work and uses the user's Claude MAX subscription tokens.
- Run entirely on the user's machine. No external services beyond Suno itself (used only by the user clicking through to suno.com with a prompt copied to clipboard).

## Non-Goals

- Not a DAW. No audio playback, no in-app generation.
- No Suno API integration in v1 (Suno's API surface is unreliable; browser handoff only).
- No multi-user collaboration in v1.
- No public hosting. Local-first only.
- No use of the Anthropic billed API. All LLM work routes through Claude Code (subscription tokens).

## Architecture

### Two surfaces, one source of truth

The system has two user-facing surfaces. Both read and write the same JSON song-state file on disk; that file is the source of truth.

```
┌──────────────────────────┐         ┌──────────────────────────┐
│   Claude Code (terminal) │         │   Web UI (localhost:3000) │
│   /song slash command    │         │   Next.js + shadcn/ui     │
│   - drives full workflow │         │   - song editor (sections) │
│   - drafts/edits lyrics  │         │   - songwriter lens picker│
│   - validates with rules │         │   - vocab/rhyme browser   │
│   - generates Suno prompt│         │   - phonetic highlighter  │
│   uses Claude MAX tokens │         │   - sonic descriptor lib  │
│                          │         │   manual editing only     │
└─────────────┬────────────┘         └─────────────┬────────────┘
              │                                    │
              │   reads/writes                     │  reads/writes
              ▼                                    ▼
       ┌────────────────────────────────────────────────────┐
       │  Shared state: ~/Songwriter/songs/<slug>.json     │
       │  (source of truth - both surfaces watch this file) │
       └────────────────────────────────────────────────────┘

       ┌────────────────────────────────────────────────────┐
       │  FastAPI backend (localhost:8000)                  │
       │  - serves the Next.js app                          │
       │  - reads SQLite for vocab/rhyme/phonetic queries   │
       │  - runs deterministic validation rules             │
       │  - writes to song JSON when UI edits sections      │
       │  - websocket file watcher for live UI sync         │
       │  - NO AI calls (those happen in Claude Code)       │
       └─────────────┬──────────────────────────────────────┘
                     ▼
       ┌────────────────────────────────────────────────────┐
       │  SQLite DB: ~/Songwriter/data/songwriter.db        │
       └────────────────────────────────────────────────────┘
```

The web UI never makes LLM calls — it is a non-AI visualization + manual-editing surface. All AI work (drafting, refining, validating with judgment, generating sonic descriptors) happens in the Claude Code skill, leveraging the user's Claude MAX x20 subscription. This avoids API costs entirely.

### Repo layout

```
songwriter/
├── apps/
│   ├── web/                # Next.js 15 app (TypeScript, Tailwind, shadcn/ui)
│   └── skill/              # Claude Code skill files (`.claude/skills/song/`)
├── services/
│   └── api/                # Python FastAPI backend
├── data/
│   ├── seeds/              # build-time scripts to construct songwriter.db
│   ├── vocab/              # YAML source files for hand-tagged vocab banks
│   ├── songwriters/        # YAML source files for songwriter profiles
│   ├── descriptors/        # YAML for pre-seeded sonic descriptors (cache primer)
│   └── songwriter.db       # built SQLite output (gitignored, regen from seeds)
├── songs/                  # user's saved song JSONs (gitignored)
├── start.sh                # boots FastAPI + Next.js together
├── install.sh              # one-time setup: deps + DB seed
└── README.md
```

YAML sources for vocab/songwriter profiles/descriptors are human-editable and compile into the SQLite DB at build time via `data/seeds/build.py`. Source-controlled, reproducible.

## Data Layer

### SQLite schema (key tables)

#### `words` — phonetic master index (~150K rows after build)

```
id                  INTEGER PK
word                TEXT (lowercased)
language            TEXT (en, es, yo, ig, pidgin, etc.)
ipa                 TEXT       # gruut/WikiPron-derived IPA
arpabet             TEXT       # CMUdict ARPAbet, English only
syllables           INTEGER
stress_pattern      TEXT       # e.g., "10" = stressed-unstressed
rhyme_class         TEXT       # last-stressed-syllable phoneme key
vowel_shape         TEXT       # short-A | long-O | diphthong-OI | ...
first_syllable_attack TEXT     # hard | soft | vowel
consonant_density   REAL       # 0.0-1.0, ratio of hard consonants
syllable_count_class TEXT      # mono | bi | multi
```

Built from: CMUdict (English ARPAbet, public domain) → derived IPA via standard ARPAbet→IPA mapping; gruut over multilingual word lists; WikiPron fallback for slang/proper nouns gruut struggles with.

#### `vocab_banks` and `vocab_bank_words` — curated emotional/genre word collections

```
vocab_banks
─────────────────
id, slug, name, description, parent_bank_id (nullable, hierarchy)
example slugs: "deathcore.destruction", "rnb.intimacy",
               "afrobeats.celebration", "grime.confrontation.london-slang"

vocab_bank_words (M-to-M with metadata)
─────────────────
bank_id, word_id
emotional_weight    REAL     # 0-1
imagery_class       TEXT     # sensory | abstract | physical | metaphorical
cliche_flag         BOOL
ai_bias_flag        BOOL     # is this a Suno token-bias word
notes               TEXT
```

#### `genres` and `sub_genres`

```
id, slug, name, parent_genre_id, description
typical_bpm_min, typical_bpm_max
default_structure_id (FK to structure_templates)
notes_for_suno      TEXT
```

12 ship genres at top level: Pop, R&B, Rap/Hip-Hop, Rock, Metal/Heavy, Country, Electronic/EDM, Latin, Folk/Singer-songwriter, Soul/Funk/Disco/Gospel, Afrobeats, UK Grime. Each has its own sub-genre tree (e.g., Pop → dance-pop, synth-pop, indie-pop, hyperpop, alt-pop, country-pop).

#### `cadence_patterns` — the 10 from the user's existing library

```
id, slug, name, syllable_template, stress_template
typical_genres      JSON
example_lines       JSON
rhyme_compatibility JSON      # which rhyme styles fit (from Rhyme-Cadence Interaction Guide)
```

Initial seed: Straight 4-Beat, Double-Time Rap, Triplet, Grime Swing, Melodic Glide, Punchline, Breakdown Chant, Pop Hook, Storytelling, Hybrid.

#### `songwriter_profiles` — the writing-style lens

```
id, slug, display_name, real_name (nullable), era, primary_genre_id
role                TEXT       # pure-songwriter | producer-songwriter |
                               # singer-songwriter | self-writing-artist
sub_genres          JSON
notable_credits     JSON       # for context only, no copyrighted lyrics
craft_signature     JSON       # studied mechanics in plain English
personality_traits  JSON
writing_style       JSON       # avg_line_syllables, rhyme_density,
                               #   internal_rhyme_freq, end_rhyme_strictness,
                               #   narrative_mode, perspective_default,
                               #   imagery_emphasis, signature_devices
preferred_cadences  JSON       # FK list to cadence_patterns
vocab_fingerprint   JSON       # signature_words, semantic_anchors,
                               #   avoided_words, vowel_priority_words
phonetic_fingerprint JSON      # vowel_preference, attack_profile, consonant_density
structure_preferences JSON
hook_style          TEXT
reference_tracks    JSON       # titles only, never lyrics
adoption_prompt     TEXT       # the system-prompt addition the skill loads
                               #   when this lens is active
```

The role distinction matters. Pure songwriter fingerprints (Diane Warren, Max Martin) generalize across performers. Self-writing artist fingerprints (Frank Ocean, Kendrick Lamar) are intrinsic to their voice. Producer-songwriter fingerprints (Stargate, Tainy, Finneas) bundle craft + production cues. Singer-songwriter fingerprints (Phoebe Bridgers, Bon Iver) tie craft to delivery.

#### `artist_descriptor_cache` — sonic translation library

```
id                  INTEGER PK
normalized_name     TEXT UNIQUE     # lowercased, stripped, no honorifics
canonical_name      TEXT            # display version
era_label           TEXT NULLABLE   # for evolving artists (e.g., "Beyoncé / Lemonade era")
descriptor          TEXT
descriptor_short    TEXT            # ~25 words for inlining into Suno prompt
descriptor_long     TEXT            # ~80-100 words for reference / regen
vocal_attributes    JSON            # gender, range, character, register, attack
production_attrs    JSON            # tempo zone, mix character, instrumentation cues
genre_context       TEXT
source              TEXT            # 'auto-llm' | 'songwriter-profile-derived' | 'user-curated'
quality_state       TEXT            # 'unverified' | 'reviewed' | 'pinned'
use_count           INTEGER DEFAULT 0
created_at, last_used_at TIMESTAMP
```

When the user references an artist by name in their direction (e.g., "sound like Frank Ocean"), the skill:
1. Normalizes the name and looks up the cache.
2. On HIT (reviewed or pinned), uses immediately, increments use_count.
3. On HIT (unverified), uses but flags in the song JSON for later review.
4. On MISS, checks if the artist has a songwriter profile with vocal/production fields — if yes, derives the descriptor from that.
5. Otherwise generates the descriptor via LLM (one-time cost), token-bias-scrubs it, and caches with `quality_state='unverified'`.
6. Splices `descriptor_short` into the Suno prompt's vocal + production lines. The artist's name never appears in the final prompt.

This is a separate concept from the songwriter profile. The two compose freely — "Diane Warren writing craft + Adele sonic descriptor" is a real legal hybrid.

#### `suno_burn_list` — token-bias avoidance

```
word, severity (mild|strong|extreme), drift_direction, alternatives JSON
```

Initial seed: Neon, Echo, Ghost, Silver, Shadow, plus ~45 more identified through the last30days research session and user testing.

#### `structure_templates` — genre-specific section orderings

```
id, name, sections JSON      # ordered list of {section, energy, syllable_target}
genre_compatibility JSON
```

#### `emotion_tempo_map` — intent-mismatch prevention

```
emotion, sub_genre_id, bpm_min, bpm_max, energy_curve, anti_prompts JSON
```

This table directly attacks the "love ballad → upbeat pop" failure. When the song JSON specifies `intent.emotion_arc` and a sub-genre, the BPM and anti-prompts are looked up from this table and locked into the Suno prompt.

#### `production_fingerprints`

```
sub_genre_id, instrumentation JSON, vocal_style JSON, mix_attributes JSON,
positive_descriptors JSON, negative_descriptors JSON  # the "NOT this" list
```

### Song state JSON shape (shared between skill and UI)

```jsonc
{
  "id": "2026-04-30-pull-me-deep",
  "title": "Pull Me Deep",
  "created": "2026-04-30T14:22:00Z",
  "modified": "2026-04-30T15:18:00Z",
  "genre": "rnb",
  "sub_genre": "alt-rnb",
  "songwriter_lens": "frank-ocean",
  "intent": {
    "topic": "late-night vulnerability with an ex",
    "emotion_arc": "longing -> confession -> surrender",
    "story": {
      "event": "she calls late, voice shaking",
      "emotion": "I should know better but I'm pulled in",
      "resolution": "I let her in anyway"
    }
  },
  "production": {
    "bpm": 72,
    "structure_template": "rnb.intimate-confession",
    "energy_curve": [0.3, 0.4, 0.7, 0.4, 0.7, 0.85, 0.7]
  },
  "sections": [
    {
      "id": "v1",
      "label": "Verse 1",
      "lock_state": "draft",
      "lyrics": ["You called me late", "Said you couldn't sleep"],
      "cadence_pattern": "melodic-glide",
      "validation": {
        "story_rule": "pass",
        "sentence_rule": "pass",
        "phonetic_texture": "pass",
        "cadence": "pass",
        "warnings": []
      },
      "phonetic_overlay": []
    }
  ],
  "suno_prompt": {
    "current": "...",
    "history": []
  },
  "requests": [],
  "notes": "free-form notes the skill picks up on next run"
}
```

### Build pipeline

`data/seeds/build.py` runs at install and on YAML edits:

1. Downloads CMUdict (4MB flat file, public domain).
2. Parses CMUdict ARPAbet → derives IPA via standard mapping.
3. Runs gruut over a curated multilingual word list (Spanish for Latin, Yoruba/Igbo/Pidgin/English for Afrobeats, English with London-slang additions for Grime).
4. Pulls WikiPron fallback entries for words gruut struggles with.
5. Computes derived fields: syllable count, stress pattern, rhyme class, vowel shape, consonant density, attack profile.
6. Loads YAML files from `data/vocab/`, `data/songwriters/`, `data/descriptors/` and joins them into the SQLite DB.
7. Writes `data/songwriter.db`.

## The Claude Code `/song` Skill

### Commands

```
/song                       Master command - launches a guided session
/song new                   Create a new song from scratch (mirrors UI wizard)
/song open <slug>           Open a song from ~/Songwriter/songs/
/song draft [section]       Draft section(s); no arg = whole song
/song refine <section>      Refine a specific section conversationally
/song alt <section> <line>  Generate 3 alternatives for a specific line
/song validate              Run all 5 rules across the song, report failures
/song lens <slug>           Apply or change the songwriter lens
/song prompt                Enter Suno prompt refinement subroutine
/song export                Final cleanup: lock all, generate final prompt, save
/song list                  List all songs
```

### The 7-step master workflow

The skill drives the user's existing 7-step workflow conversationally:

1. **Story Rule** — skill prompts user for event/emotion/resolution.
2. **Sentence Rule** — after each draft, every line passes the 4-check validation.
3. **Phonetic Texture Rule** — skill queries DB for vocab matching emotion + attack profile + lens fingerprint.
4. **Cadence Rule** — skill picks cadence per section, validates stress alignment.
5. **Genre Pattern** — `structure_template` + `production_fingerprint` loaded from DB.
6. **Final Validation** — all 5 rules run; failures get fixed before export.
7. **Suno Prompt** — the prompt refinement subroutine.

At each step the skill writes its output to the song JSON. The web UI live-updates as the skill works.

### Per-line draft request handling

When validation fails OR the user manually requests alternatives in the UI, the UI writes a request entry into the song JSON:

```jsonc
"requests": [
  { "type": "suggest_alternatives", "section": "v2", "line": 3, "count": 3, "constraint": "more vulnerable" }
]
```

The skill, on its next run, sees the request, drafts alternatives constrained by the section's cadence + lens + genre vocab bank, writes them back, and clears the request. The UI re-renders inline.

### `/song prompt` — Suno prompt refinement subroutine

A 5-phase loop:

**Phase 1 — Direction Capture.** Skill asks: *"Give me your starting direction for the Suno prompt — one or two sentences."*

**Phase 2 — Targeted Clarification.** Skill loads the genre's `production_fingerprints` row, identifies underspecified fields, asks 4-7 questions one at a time. Questions are pulled from required fields, never improvised. Different question sets for different genres.

**Phase 2a — Artist-name detection + descriptor lookup.** If user input contains a likely artist name (e.g., "feel like Tyla but darker"), skill extracts the name(s), runs the descriptor cache pipeline (cache → profile-derived → LLM-generated, in that order), and uses `descriptor_short` for the prompt.

**Phase 3 — Draft + Anti-Prompt Construction.** Skill assembles the prompt using the user's existing 9-section framework plus:
- Token bias scrub against `suno_burn_list`
- Anti-prompt block from `production_fingerprints.negative_descriptors` + `emotion_tempo_map.anti_prompts`
- BPM lock from `emotion_tempo_map`
- Songwriter lens craft cues if a lens is active
- Section dynamics from `production.energy_curve`

**Phase 4 — Refinement Loop.** Outputs the draft with character count. User can refine conversationally ("add tape warmth", "less reverb", "final chorus needs to soar"). Each refinement is logged in `suno_prompt.history`.

**Phase 5 — Final Output.** Writes final prompt to `suno_prompt.current`. UI Suno tab live-updates. User clicks "Open in Suno" → prompt copied + suno.com opens.

### Standalone direction-improvement mode

`/song prompt --improve "<existing prompt>"` runs an existing prompt through the same probe-clarify-rebuild loop, diagnoses what was missing, asks only the questions needed to fix gaps, rebuilds.

### Constraints

- Never invents reference artists in output ("write like Frank Ocean") — only uses the songwriter-lens or sonic-descriptor system internally.
- Never includes copyrighted lyrics in any prompt or draft.
- Never bypasses validation — every drafted line goes through all 5 rules before saving.
- Never writes outside the song JSON — all skill output funnels through the same file.

## The Web UI (Next.js + shadcn/ui)

### Visual style baseline

Dark mode default. shadcn/ui components, Geist for UI text, a serif (Lora or EB Garamond) for the lyric editor itself. Generous whitespace. No gradients. Subtle phonetic-overlay color (warm red for hard consonants, cool blue for sustained vowels, thin underline for stressed syllables).

### Pages

#### Home / Song Library (`/`)

Hero card "Start a new song", grid of recent songs as cards with title / genre / lens chip / last-edited / lock-state summary. Sidebar filter by genre, search by title/topic. Top right: settings, songwriter profiles, vocab browser, sonic descriptors.

#### New Song Wizard (`/songs/new`)

6 steps, one question per screen:
1. Genre — 12 large cards
2. Sub-genre — narrows
3. Topic — free text
4. Emotion arc — escalation / collapse / redemption / surrender / defiance / custom
5. Songwriter lens (optional) — searchable chip-grid filtered to the genre, role badge + craft signature + 1 notable credit per card. Big "Skip lens" option.
6. Review → "Create song" → opens editor

After step 6, a banner reads: *"Run `/song draft` in Claude Code to generate the first pass."* with a copy button.

#### Song Editor (`/songs/[slug]`)

Three-pane layout:
- **Left rail:** Sections list with drag-to-reorder, lock states (● drafted, 🔒 locked), "+ Add section" using genre's structure template.
- **Center canvas:** Section header with cadence + syllable summary; lyrics in serif type, double-spaced; phonetic overlay toggle (off / consonants / vowels / full); inline validation chips per rule; per-line action menu.
- **Right rail tabs:**
  - **Vocab** — selected word's phonetic data, vocab bank membership, alternatives.
  - **Rhymes** — for the focused line: end rhymes, internal rhyme candidates, slant rhymes by vowel class. Sortable by syllable count and consonant attack.
  - **Cadence** — beat-grid visualization of stress pattern; "tighten to triplet" / "stretch to melodic-glide" buttons emit JSON requests for the skill.
  - **Suno** — live preview of current prompt with character count, anti-prompts, lens additions; copy button; Open in Suno button.
  - **Notes** — free-form, the skill reads on next run.
- **Bottom production bar:** BPM slider, energy curve sparkline, structure template selector.

#### Songwriter Profiles (`/songwriters`)

Searchable grid filtered by role + genre. Profile detail page shows full craft signature, vocab fingerprint, preferred cadences, sample-size visualizations. "Use this lens for next song" CTA.

#### Sonic Descriptor Library (`/descriptors`)

Searchable table: name / canonical / source / quality_state / use_count / last_used. Detail view with editable descriptor (short + long), regenerate button, pin button. Review queue filter for unverified entries. Compose view: pair one descriptor with one songwriter profile, preview the combined system-prompt result.

#### Vocab Bank Explorer (`/vocab`)

Tree view: genre → sub-genre → bank. Click a bank → table of words with phonetic data, emotional weight, cliche flag, AI-bias flag. Search across all banks. Add custom bank (creates a YAML in `data/vocab/custom/`).

#### Settings (`/settings`)

Song save folder, songwriter lens defaults per genre, phonetic overlay color preferences, default BPM behavior, DB rebuild button.

### Live JSON sync

The UI uses a websocket to FastAPI that file-watches `~/Songwriter/songs/`. When the skill writes, the UI live-updates within ~200ms with a subtle highlight on changed sections. UI manual edits write to JSON immediately; the skill picks up changes on its next run.

### What the UI explicitly does NOT do

- No LLM calls (no API key needed)
- No streaming AI text (Claude Code's job)
- No music playback (not a DAW)
- No direct Suno API (browser handoff only)

## Validation Rule Engines

Each of the 5 rules from the user's framework gets a checker. Checkers are partly deterministic (DB-driven) and partly Claude-judged (the skill makes the call):

| Rule | Method |
|---|---|
| **Sentence Rule** — Sentence Logic | Hybrid: simple grammar/parsing checks deterministic; semantic plausibility is Claude-judged. |
| **Sentence Rule** — Context Continuity | Claude-judged (compares line N to N-1 and N+1). |
| **Sentence Rule** — Narrative Consistency | Claude-judged against `intent.story`. |
| **Sentence Rule** — Singability | Deterministic via `cadence_patterns` + `words.stress_pattern` lookup. |
| **Story Rule** | Claude-judged: confirms event + emotion + resolution all present in song structure. |
| **Phonetic Texture Rule** | Deterministic: every content word's `consonant_density` + `first_syllable_attack` checked against the section's emotion target. Flags mismatches. |
| **Cadence Rule** | Deterministic: stress pattern of each line compared to the section's `cadence_patterns.stress_template`. |
| **Rhyme-Cadence Interaction** | Deterministic: rhyme style selected for the section checked against `cadence_patterns.rhyme_compatibility`. |

Validation results write to `sections[i].validation` in the song JSON. UI shows green/yellow/red chips per rule.

## Phasing

### Phase 1 — Today's session (one-day MVP)

End-to-end working skeleton with 2 genres seeded deeply enough to write real songs.

**Ships:**
- Full repo scaffold (Next.js + FastAPI + SQLite + skill folder)
- Complete DB schema + migration scripts
- CMUdict ingestion + gruut English IPA pipeline
- All 5 validation rule engines (deterministic + Claude-judged hybrid)
- FastAPI with all lookup endpoints + file watcher + websocket sync
- Next.js home + wizard + song editor + Vocab/Suno tabs
- Claude Code `/song` skill, all commands, end-to-end working
- `/song prompt` refinement loop with sonic-descriptor cache
- Install/start scripts
- 2 genres seeded (Pop + R&B): ~12 vocab banks, ~10 songwriter profiles, ~10 pre-seeded sonic descriptors, BPM map, burn list (~50 words)
- Working test song: blank → final Suno prompt by end of session

**Phase 1 success criteria:**
1. Write a complete pop song from blank → final Suno prompt in one session.
2. All 5 rules pass on the final lyrics; no burn-list words in the final prompt.
3. Same workflow works on R&B with zero code changes (only DB content differs).
4. Songwriter lens produces a visibly different draft than no-lens (rhyme density measurably lower with Frank Ocean lens vs blank).
5. Web UI live-updates within ~200ms of skill writes.
6. Section editing in the UI persists to JSON; skill respects locks on next run.
7. Sonic descriptor cache works: second reference to the same artist name = zero LLM cost.

### Phase 2 — Genre breadth expansion (subsequent sessions)

Remaining 10 genres' vocab banks (Rock, Metal/Heavy, Country, Electronic/EDM, Latin, Folk, Soul-Funk-Disco-Gospel, Afrobeats, UK Grime, Rap/Hip-Hop). Multilingual phonetic data (Spanish, Yoruba, Igbo, Pidgin). ~45 more songwriter profiles. 30-40 more pre-seeded sonic descriptors. UI: full Songwriter Profiles browser, Sonic Descriptor Library, Vocab Bank Explorer, Cadence inspector + Rhymes tabs. Visual polish.

### Phase 3 — Power-user depth + research integration

`/last30days` integration: `/song research <artist>` updates songwriter profiles from current discussion; `/song research <genre> trends` surfaces emerging slang and Suno pitfalls. Trait-based hybrid lens composition. UI-authored vocab banks. Energy-curve drag-editor. Advanced phonetic visualizations. Batch operations. Sonic-descriptor review queue UI.

### Phase 4 — Optional / nice-to-haves

Tauri wrap for native desktop install. Profile/bundle export. Audio preview via Tone.js + TTS. Suno API integration if/when it becomes real. Multi-user collaboration.

## Risks

1. **Multilingual phonetic quality** — gruut's IPA for Yoruba/Pidgin/London-slang is uneven. Expect 70-80% accuracy day one; WikiPron fallbacks + manual overrides for Afrobeats and Grime. Plan for this in Phase 2.
2. **Validation rules are prose** — the user's existing 5 rules are in plain English. Some checks are inherently judgment calls and must run as Claude-judged validations in the skill. Each rule's check method is formalized in the table above.
3. **Token economy** — Claude MAX is generous but multi-step workflows on long songs can hit context limits. Skill loads only relevant DB rows per step, not the whole DB.
4. **UI/skill JSON sync race conditions** — both surfaces editing simultaneously. Last-write-wins with a `last_modified_by` field + diff banner on conflict.
5. **Suno itself drifts** — what works April 2026 may slop October 2026. The descriptor cache `quality_state` lets us flag stale entries. Burn list refresh quarterly.

## Open Questions

None — all answered during brainstorm:
- Workflow shape: linear multi-step with section-by-section editing.
- Tool shape: Claude Code skill primary + polished Next.js web UI secondary.
- Phonetic depth: hybrid B+C — borrow open-source data (CMUdict + gruut + WikiPron + espeak-ng), encode at IPA-grade, hand-tag the curated emotional/genre layer, programmatic phonemizer for the long tail.
- Genre scope: 12 (added Afrobeats and UK Grime to original 10).
- Songwriter vs artist: songwriter-weighted with role classification.
- Sonic descriptors: separate cache, distinct from songwriter profiles.
- Billing: Claude MAX subscription via Claude Code, no Anthropic billed API.

## Out of Scope (recap)

- DAW features
- Suno API integration
- Multi-user / collaboration
- Public hosting
- Anthropic billed API usage
- Use of any copyrighted lyric material in the DB or output
