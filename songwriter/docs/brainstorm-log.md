# Songwriter — Improvement Brainstorm Log

Ideas generated autonomously every 20 minutes.
Review with the user to decide what to build next.


---
## [2026-05-02 03:56] Session — Focus: A. Lyric Quality

### 1. Rhyme-First Line Construction via Pre-Committed Rhyme Pairs
**Problem:** `_INITIAL_PROMPT` in `draft.py` tells the LLM "Pick the rhyme word FIRST, then write the line around it" (Rule 5), but this is advisory text buried after six other rules. The LLM has already committed to imagery and line structure before it encounters Rule 5. The repair prompt in `_REPAIR_PROMPT` says "pick the correct rhyme word first, then rewrite both lines of the pair" — but by repair time, the surrounding lines constrain what rhymes are possible. The output samples confirm the problem: "deal/smooth" and "up/smooth" are near-misses, not intentional rhyme pairs.
**Idea:** Force rhyme pair pre-commitment by splitting generation into two explicit phases: first, emit a `rhyme_plan` object (just end-words per line), then fill in the full lines constrained by that plan. Inject the approved rhyme pairs back into `_INITIAL_PROMPT` as a structured constraint block above the section body.
**How:** In `draft.py`, add a short PRE-DRAFT prompt (~200 tokens out, `GENERAL` task) that asks the LLM to output only `{"rhyme_plan": {"v1": ["A","A","B","B"], "endwords": {"v1": ["hit","lit","bag","flag"]}}}` for the target sections. Parse that JSON, then inject a `RHYME CONTRACT` block into `_INITIAL_PROMPT` above `RULES:` like: `RHYME CONTRACT — end every line with exactly these words (in order): hit, lit, bag, flag`. Modify `sections_for_genre` return dicts to carry a `rhyme_scheme` field (`AABB`, `ABAB`, etc.) per section type so the pre-draft call knows the pattern. New helper `_build_rhyme_contract(rhyme_plan) -> str` in `draft.py`.
**Effort:** M
**Impact:** Eliminates the most common user complaint — lines that almost rhyme but don't. Forces the LLM into a constrained fill-in-the-blank mode where creative failure is localized to meter, not rhyme.

---

### 2. Section-Role Awareness in the Draft Prompt
**Problem:** `_INITIAL_PROMPT` receives a flat `{section_block}` for all four sections at once (v1, ch1, v2, ch2 as defined in `sections_for_genre`). There is no per-section instruction about *what job that section must do narratively*. Verse 1 should establish the world, Chorus should deliver the emotional hook, Verse 2 should escalate or complicate, Chorus 2 should land differently from Chorus 1. Currently the LLM treats all four sections as interchangeable lyric containers — hence the sample output where `[Chorus]` and `[Verse 1]` have nearly identical energy and imagery.
**Idea:** Add a `section_roles` block to `_INITIAL_PROMPT` that gives each section a one-line dramatic directive: `v1: Establish the world — name one character, one location, one problem. ch1: Land the emotional thesis in one repeatable line. v2: Escalate — something changed since v1. ch2: Same hook, but earned — the listener now understands why it hurts.`
**How:** In `draft_defaults.py`, extend `sections_for_genre` to return a `role` field per section dict: `{"id": "v1", "label": "Verse 1", "cadence": v, "role": "Establish the world..."}`. In `draft.py`, build a `SECTION ROLES` block from these roles and inject it between `=== SECTIONS TO WRITE ===` and `{lens_brief}` in `_INITIAL_PROMPT`. Add the same block to `_REPAIR_PROMPT` so repairs don't lose section identity. Roles should vary by genre: a trap verse role differs from a folk verse role — add a `_SECTION_ROLES` dict to `draft_defaults.py` keyed by the same genre slugs as `_GENRE_CADENCES`.
**Effort:** S
**Impact:** Stops the chorus from sounding like a verse and vice versa. Users get songs with real narrative arc instead of four stanzas of the same emotional intensity.

---

### 3. Burn-Word Expansion from Actual Failures via Repair Feedback Loop
**Problem:** `_INITIAL_PROMPT` includes `AVOID: {burn_words}` and `_REPAIR_PROMPT` does the same, but `burn_words` is a static list resolved at call time — there is no mechanism to accumulate words that *actually failed validation* during the current draft loop. When `rhyme_cadence` or `singability` checks fail in `validate_song` (called in `draft.py`'s loop), the failing lines are sent to repair, but the repair prompt has no memory of *which specific words caused the failure*. The LLM often substitutes a word with the same flaw.
**Idea:** After each `validate_song` call in the draft loop, extract the actual end-words from lines that received `rhyme_cadence: fail` verdicts (visible in `SectionValidation`) and the polysyllabic clusters from `phonetic_texture: fail` lines, then inject them as *dynamic burn words* into the next `_REPAIR_PROMPT` call: `DO NOT USE THESE SPECIFIC WORDS (they already failed): sealed, through, still, clusters`.
**How:** In `draft.py`'s repair loop, after `validate_song` returns the updated `Song`, add a function `_extract_failure_tokens(song: Song) -> list[str]` that walks `section.validation.rhyme_cadence` and `section.validation.phonetic_texture` for `verdict == "fail"`, pulls the offending tokens from `section.validation.warnings` (already populated by `rhyme_cadence.check_section` and `phonetic_texture.check_line` in `orchestrator.py`), and returns a deduplicated list. Pass this as `dynamic_burn_words` into `_REPAIR_PROMPT` formatting, appended after `{burn_words}`. Cap at 20 tokens to avoid prompt bloat.
**Effort:** S
**Impact:** Breaks the repair loop out of local minima. Instead of swapping "sealed" for "steel" (same phonetic flaw), the LLM is explicitly blocked from the failure space and must find a genuinely different solution.

---

### 4. Verse-2 Differentiation Constraint (No Line Recycling)
**Problem:** `sections_for_genre` produces `v1` and `v2` with identical cadence patterns and no constraint preventing lyric similarity. In the draft loop in `draft.py`, both verses are generated in the same `_INITIAL_PROMPT` call with no instruction that v2 must differ from v1. The sample song "hustle" shows this plainly: `[Verse 1] 'Phone ring once, I already see the bag'` and `[Chorus] 'Phone ring, I get paid'` — the same image recycled across sections. With v2 also present, this gets worse.
**Idea:** After DRAFT generation (step 1 of the loop), before validation, run a fast similarity check between v1 and v2 lines using token overlap (no LLM call). If Jaccard similarity of unigrams exceeds 0.35
---


---
## [2026-05-02 03:57] Session — Focus: A. Lyric Quality

### 1. Rhyme-First Line Scaffolding via Pre-Committed End-Words
**Problem:** `_INITIAL_PROMPT` includes the instruction "Pick the rhyme word FIRST, then write the line around it — never the reverse" but this is advisory text only — the LLM still receives a blank slate and regularly buries a weak rhyme word at line-end because it wrote the line first. The repair samples confirm this: `rhyme_cadence` is among the most common repair triggers. The prompt tells the LLM *how to think* but gives it nothing structural to commit to before the line is written.
**Idea:** Inject a pre-committed rhyme scaffold block into `_INITIAL_PROMPT` — a JSON stub that declares the end-words for each rhyme pair *before* the LLM writes a single line. The LLM fills in the interior of each line but cannot change the end-words. The scaffold is generated by a lightweight `_build_rhyme_scaffold(sections, song)` function using a curated rhyme-pair lookup, not the LLM, so it's deterministic and fast.
**How:** In `draft.py`, before formatting `_INITIAL_PROMPT`, call `_build_rhyme_scaffold(target_sections, song)` which returns a dict like `{"v1": [["crown","down"], ["gate","late"]], "ch1": [["free","we"], ...]}`. Serialize this as a `RHYME SCAFFOLD` block appended to the prompt: `"v1 line-1 ends: 'crown', line-2 ends: 'down' — write lines that land naturally on these words."` Source end-words from `song.intent.story` keywords and `anchor_words` already resolved by `resolve_vocab` in `draft.py`, filtering to known CMU-rhyming pairs via the existing phonetic machinery in `validation/rhyme_cadence.py`. Cap each section at 3 pairs. This costs zero LLM calls and removes the most common failure mode at the source.
**Effort:** M
**Impact:** Eliminates the class of `rhyme_cadence: fail` where the LLM wrote a good line then chose an unrhymable end-word. Users get first-draft lyrics where pairs already land — repair rounds shrink from 2 to near-zero for rhyme failures.

---

### 2. Narrative Position Tags to Break Flat Emotional Arcs
**Problem:** `sections_for_genre` in `draft_defaults.py` assigns cadence patterns but nothing tells the LLM *where in the story* each section sits. Both `v1` and `v2` receive the same prompt context in the single `_INITIAL_PROMPT` call in `draft.py`. The result is flat intensity — v2 reads like a restatement of v1 rather than an escalation, and the chorus repeats the same emotional register each time it appears. The sample "hustle" confirms this: `[Verse 1] 'Phone ring once, I already see the bag'` and `[Chorus] 'Phone ring, I get paid'` — same tension, same image, same emotional beat.
**Idea:** Add a `narrative_position` field to each section dict in `sections_for_genre` in `draft_defaults.py`, with values like `"setup"`, `"tension"`, `"release"`, `"escalation"`, `"payoff"`. Inject these into `_INITIAL_PROMPT`'s `SECTIONS TO WRITE` block so each section label reads: `"v1 (Verse 1 — SETUP: introduce the world and the want)"`, `"ch1 (Chorus — RELEASE: state the core feeling, not the situation)"`, `"v2 (Verse 2 — ESCALATION: something has changed or been lost)"`.
**How:** In `draft_defaults.py`, define a `_NARRATIVE_POSITIONS` dict keyed by section id pattern (`"v1"`, `"v2"`, `"ch1"`, `"ch2"`, `"bridge"`) with short imperative descriptions. Update `sections_for_genre` to attach `narrative_position` to each returned dict. In `draft.py`'s `_build_section_block` (or wherever the section list is serialized into `{section_block}`), append the position label in parentheses. No LLM cost, no validation change — pure prompt signal.
**Effort:** S
**Impact:** Gives users songs with actual dramatic arc. v2 advances the story instead of restating it. The chorus lands as emotional release rather than a louder version of the verse. This is the difference between a song that feels like it *goes somewhere* versus one that loops.

---

### 3. Concrete-Image Density Gate Before LLM Story Check
**Problem:** `story_sentence.check_section` in `orchestrator.py` runs an LLM call (Gemini Flash) to check for abstraction — but it fires on *every* section, including ones that are already concrete. The real problem is that abstractness is introduced silently during generation: lines like "I feel the pain" or "we rise above" pass `singability` and `rhyme_cadence` checks fine but are creatively dead. The LLM story check catches some of these but it's expensive and catches them late. There is no pre-LLM signal that a section has collapsed into abstraction.
**Idea:** Add a `_abstract_ratio(lines: list[str]) -> float` function in `validation/story_sentence.py` (or a new `validation/concreteness.py`) that counts lines containing a curated set of abstract copula patterns — `"(is|are|was|were|feel[s]?|seems?) (the|a|so|too|like)"`, pronoun-only subjects with emotion verbs (`"I (feel|know|believe|need|want)"` without a noun object), and lines under 4 content words. If the ratio exceeds 0.4, flag the section as `concrete_density: warn` before the LLM call runs. Inject the flagged lines back into the repair prompt as a distinct `ABSTRACTION FAILURES` block, separate from the existing `HOW TO FIX` section.
**How:** In `orchestrator.py`'s `validate_song`, run `_abstract_ratio` synchronously before the `ThreadPoolExecutor` block that fires `story_sentence.check_section`. Attach the result to `SectionValidation` as a new `concrete_density` field (add to `schemas.py`). In `draft.py`'s repair loop, when building `_REPAIR_PROMPT`'s `failing_block`, include a line-by-line callout: `"line 3 — too abstract, no concrete noun: replace with a specific object from the world."` This costs no LLM calls and gives the repair prompt richer signal than the current single-word verdict.
**Effort:** M
**Impact:** Stops abstract filler lines from surviving past the first draft. Users get verses where every line has a thing in it — an object, a place, a body part, an action with a subject — instead of vague emotional affirmations that could appear in any song ever written.

---

### 4. Hook Payoff Line Isolation and Repetition Scoring
**Problem:** The chorus is the most repeated, most remembered part of any song, but `_INITIAL_PROMPT` treats chorus lines identically to verse lines. There is no instruction that the final line of a chorus (`ch1`, `ch2`) should function as a *hook payoff* — a short, singable,
---


---
## [2026-05-02 04:08] Session — Focus: A. Lyric Quality

### 1. Enforce Explicit Rhyme Scheme per Section
**Problem:** The current `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter
---


---
## [2026-05-02 08:40] Session — Focus: B. UX & Workflow

### 1. User-Controlled Section Locking and Targeted Regeneration
**Problem:** The current `POST /songs/{slug}/draft` route described in `src/songwriter/api/routes/draft.
---


---
## [2026-05-02 09:41] Session — Focus: C. Genre & Music Theory

### 1. Integrate Explicit Chord Progression Hinting in Prompts
**Problem:** The `_SYSTEM_PROMPT` in `src/songwriter/api/llm.py` explicitly states
---


---
## [2026-05-02 10:41] Session — Focus: D. Cost & Speed

### 1. Optimize Redundant System Prompt for Repair Tasks
**Problem:** The `_SYSTEM_PROMPT` in `src/songwriter/api/llm.py` is a
---


---
## [2026-05-02 11:41] Session — Focus: E. Suno Integration

### 1. Enhance Suno Prompt Generation with Musical Style and Instrumentation Hints
**Problem:** The `src/songwriter/api/llm.py` file defines a `SUNO
---


---
## [2026-05-02 12:41] Session — Focus: F. Wild Card

### 1. Dynamic `MAX_ATTEMPTS` based on Initial Draft Quality
**Problem:** The `POST /songs/{slug}/draft` route in `src/songwriter/api/routes/
---


---
## [2026-05-02 13:41] Session — Focus: A. Lyric Quality

### 1. Elevate Rhyme Quality with Specificity Beyond Sound
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py` instructs "
---


---
## [2026-05-02 14:41] Session — Focus: B. UX & Workflow

### 1. Iterative Section Generation and Contextual Prompts
**Problem:** The `POST /songs/{slug}/draft` route in `src/songwriter/api/routes/draft.
---


---
## [2026-05-02 15:42] Session — Focus: C. Genre & Music Theory

### 1. Dynamic "Burn Words" and "Encourage Words" based on Genre and Sub-Genre
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_
---


---
## [2026-05-02 16:42] Session — Focus: D. Cost & Speed

### 1. Context-Aware `_REPAIR_PROMPT` Condensation
**Problem:** The `_REPAIR_PROMPT` in `src/songwriter/api/routes/
---


---
## [2026-05-02 17:42] Session — Focus: E. Suno Integration

### 1. Integrate Genre-Specific BPM and Key Metadata for Suno Prompts
**Problem:** The `SUNO` task in `src/songwriter/api/llm.py`
---


---
## [2026-05-02 18:42] Session — Focus: F. Wild Card

### 1. User-Defined Custom Validators via Plugin System
**Problem:** The current validation suite in `src/songwriter/api/validation/orchestrator.py` is fixed, comprising checks
---


---
## [2026-05-02 19:42] Session — Focus: A. Lyric Quality

### 1. Enforce Progressive Narrative Beats per Section
**Problem:** While `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter/api
---


---
## [2026-05-02 20:42] Session — Focus: B. UX & Workflow

### 1. Incremental Section-by-Section Generation
**Problem:** The `POST /songs/{slug}/draft` route in `src/songwriter/api/routes/draft.py`
---


---
## [2026-05-02 21:43] Session — Focus: C. Genre & Music Theory

### 1. Granular Cadence Pattern Specification & Mixing
**Problem:** The `_GENRE_CADENCES` mapping in `src/songwriter/api/routes/draft_
---


---
## [2026-05-02 22:43] Session — Focus: A. Lyric Quality

### 1. Elevate Thematic Consistency with "World Objects" Instruction
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter/
---


---
## [2026-05-02 23:43] Session — Focus: B. UX & Workflow

### 1. Granular Real-time Progress Feedback During Draft Generation
**Problem:** The `POST /songs/{slug}/draft` route involves a multi-step loop with LLM calls
---


---
## [2026-05-03 00:43] Session — Focus: C. Genre & Music Theory

### 1. Integrate Chord Progression Moods into LLM Prompts
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/
---


---
## [2026-05-03 01:43] Session — Focus: D. Cost & Speed

### 1. Dynamic `DRAFT` Task Token Limit Based on Section Count
**Problem:** The `TASK_MAX_TOKENS["DRAFT"]` is a fixed `1
---


---
## [2026-05-03 02:43] Session — Focus: E. Suno Integration

### 1. Generate Structured Suno Style Prompts from Song Context
**Problem:** The `SUNO` task in `src/songwriter/api/llm.py` is routed to
---


---
## [2026-05-03 03:44] Session — Focus: F. Wild Card

### 1. LLM Prompt Versioning and A/B Testing Framework
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter
---


---
## [2026-05-03 04:44] Session — Focus: A. Lyric Quality

### 1. Granular Rhyme Scheme Specification and Pre-selection Instruction
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py`
---


---
## [2026-05-03 05:44] Session — Focus: B. UX & Workflow

### 1. Section Locking to Preserve User Edits
**Problem:** The current `POST /songs/{slug}/draft` route orchestrates a loop of generation and repair. If a user
---


---
## [2026-05-03 06:44] Session — Focus: C. Genre & Music Theory

### 1. Dynamic Anchor Vocabulary Prioritization by Emotional Arc
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py`
---


---
## [2026-05-03 07:44] Session — Focus: D. Cost & Speed

### 1. Adaptive Repair Loop with Early Exit
**Problem:** The `MAX_ATTEMPTS = 2` constant in `src/songwriter/api/routes/draft.py
---


---
## [2026-05-03 08:44] Session — Focus: E. Suno Integration

### 1. Infer Instrumentation and Arrangement Hints for Suno Prompts
**Problem:** The `SUNO` task in `src/songwriter/api/llm.py` is
---


---
## [2026-05-03 09:44] Session — Focus: F. Wild Card

### 1. Song Versioning and Diffing for Iteration Tracking
**Problem:** The `write_song` function in `src/songwriter/api/songs_io.py` saves the current
---


---
## [2026-05-03 10:45] Session — Focus: A. Lyric Quality

### 1. Dynamic Negative Constraints to Avoid Generic Genre Tropes
**Problem:** The `_SYSTEM_PROMPT` in `src/songwriter/api/llm.py` and rules in
---


---
## [2026-05-03 11:45] Session — Focus: B. UX & Workflow

### 1. User-Controlled "Retry Harder" for Draft Generation
**Problem:** The `MAX_ATTEMPTS = 2` constant in `src/songwriter/api
---


---
## [2026-05-03 12:45] Session — Focus: C. Genre & Music Theory

### 1. Granular Cadence Pattern Specification and Customization
**Problem:** The `_GENRE_CADENCES` mapping in `src/songwriter/api/routes/draft_defaults
---


---
## [2026-05-03 13:45] Session — Focus: A. Lyric Quality

### 1. Enhanced "World Lexicon" Prompting for Deeper Integration
**Problem:** While the `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py
---


---
## [2026-05-03 14:45] Session — Focus: B. UX & Workflow

### 1. Granular "Regenerate Section" Action
**Problem:** The `POST /songs/{slug}/draft` route orchestrates a loop for generating and repairing the *
---


---
## [2026-05-03 15:45] Session — Focus: C. Genre & Music Theory

### 1. Contextual Cadence Selection Based on Song Intent & Section Function
**Problem:** The `_GENRE_CADENCES` dictionary in `src/songwriter/api/
---


---
## [2026-05-03 16:46] Session — Focus: D. Cost & Speed

### 1. Dynamic Token Budget Allocation for DRAFT/REPAIR
**Problem:** The `TASK_MAX_TOKENS` dictionary in `src/songwriter/api/llm.py`
---


---
## [2026-05-03 17:46] Session — Focus: E. Suno Integration

### 1. Explicit BPM, Key, and Tempo Hint Generation for Suno
**Problem:** The `SUNO` task in `src/songwriter/api/llm.py` currently
---


---
## [2026-05-03 18:46] Session — Focus: F. Wild Card

### 1. User-Configurable LLM Provider & Model Selection
**Problem:** The `src/songwriter/api/llm.py` module hardcodes LLM providers and models
---


---
## [2026-05-03 19:46] Session — Focus: A. Lyric Quality

### 1. Progressive Section Generation with LLM Memory/Context
**Problem:** The current `POST /songs/{slug}/draft` route states "1. Generate all target sections in one call
---


---
## [2026-05-03 20:46] Session — Focus: B. UX & Workflow

### 1. Real-time, Granular Progress Feedback via WebSockets
**Problem:** The `POST /songs/{slug}/draft` route's description outlines a multi-step loop
---


---
## [2026-05-03 21:46] Session — Focus: C. Genre & Music Theory

### 1. Dynamic Anchor Vocabulary Generation & Refinement
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter/api/
---


---
## [2026-05-03 22:47] Session — Focus: D. Cost & Speed

### 1. Dynamic Prompt Context for Repair Calls
**Problem:** The `_REPAIR_PROMPT` in `src/songwriter/api/routes/draft.py` includes
---


---
## [2026-05-03 23:47] Session — Focus: E. Suno Integration

### 1. Generate Suno-Specific Musical Style & Instrumentation Prompts
**Problem:** The `SUNO` task defined in `src/songwriter/api/llm.py
---


---
## [2026-05-04 00:47] Session — Focus: F. Wild Card

### 1. Song Structure Editor and Customization
**Problem:** The `sections_for_genre` function in `src/songwriter/api/routes/draft_defaults.py` provides
---


---
## [2026-05-04 01:47] Session — Focus: A. Lyric Quality

### 1. Dedicated "World Adherence" Validation and Repair
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py` explicitly
---


---
## [2026-05-04 02:47] Session — Focus: B. UX & Workflow

### 1. User-Controlled Iteration Attempts for Draft Generation
**Problem:** The `MAX_ATTEMPTS = 2` constant in `src/songwriter/api/routes
---


---
## [2026-05-04 03:47] Session — Focus: C. Genre & Music Theory

### 1. User-Configurable Custom Cadence Patterns
**Problem:** The `_GENRE_CADENCES` dictionary in `src/songwriter/api/routes/draft_defaults.
---


---
## [2026-05-04 04:48] Session — Focus: A. Lyric Quality

### 1. Dynamic "Show, Don't Tell" Enforcement with LLM Feedback
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/
---


---
## [2026-05-04 05:48] Session — Focus: B. UX & Workflow

### 1. Selective Section Regeneration or Targeted Repair
**Problem:** The `POST /songs/{slug}/draft` route's description notes that the system "Generate all target sections in one call"
---


---
## [2026-05-04 06:48] Session — Focus: C. Genre & Music Theory

### 1. Sub-genre Specific "Genre Craft" Instructions
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter
---


---
## [2026-05-04 07:48] Session — Focus: D. Cost & Speed

### 1. Dynamic `MAX_ATTEMPTS` Based on Initial Draft Quality
**Problem:** The `MAX_ATTEMPTS = 2` constant in `src/songwriter
---


---
## [2026-05-04 08:48] Session — Focus: E. Suno Integration

### 1. User-Guided Refinement of Generated Music Style Prompts
**Problem:** The previous brainstorm session identified the need to "Generate Suno-Specific Musical Style & Instrumentation Prompts
---


---
## [2026-05-04 09:48] Session — Focus: F. Wild Card

### 1. LLM Prompt Versioning and A/B Testing System
**Problem:** The core LLM prompts like `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in
---


---
## [2026-05-04 15:10] Session — Focus: A. Lyric Quality

### 1. Dynamic, Failure-Specific Repair Instructions
**Problem:** The `_REPAIR_PROMPT` in `src/songwriter/api/routes/draft.py` uses generic
---


---
## [2026-05-04 16:10] Session — Focus: B. UX & Workflow

### 1. Detailed Line-by-Line Validation Feedback
**Problem:** The `POST /songs/{slug}/draft` route description states "Run deterministic validation (syllable, rhyme
---


---
## [2026-05-04 17:11] Session — Focus: C. Genre & Music Theory

### 1. User-Defined Genre Vocabulary & Rules
**Problem:** The system currently relies on hardcoded `_GENRE_CADENCES` in `src/songwriter/api/routes/
---


---
## [2026-05-04 18:11] Session — Focus: D. Cost & Speed

### 1. Contextual Compression for `_REPAIR_PROMPT`
**Problem:** The `_REPAIR_PROMPT` in `src/songwriter/api/routes/
---


---
## [2026-05-04 19:11] Session — Focus: E. Suno Integration

### 1. Granular Instrumentation and Arrangement Generation for Suno
**Problem:** The `src/songwriter/api/llm.py` file defines a `SUNO` task with a limited
---


---
## [2026-05-04 20:11] Session — Focus: F. Wild Card

### 1. LLM Provider Hot-Swapping for Advanced Users
**Problem:** The `src/songwriter/api/llm.py` module explicitly routes tasks like "DRAFT
---


---
## [2026-05-04 21:11] Session — Focus: A. Lyric Quality

### 1. Dynamic "World Adherence" Validation and Repair
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py` explicitly
---


---
## [2026-05-04 22:11] Session — Focus: B. UX & Workflow

### 1. Section Locking for User-Edited Content
**Problem:** The `POST /songs/{slug}/draft` route's described loop ("send ONLY the failing sections back for targeted repair")
---


---
## [2026-05-04 23:33] Session — Focus: C. Genre & Music Theory

### 1. Granular Cadence Pattern Selection for Diverse Section Types
**Problem:** The `_GENRE_CADENCES` dictionary in `src/songwriter/api/routes/
---


---
## [2026-05-05 00:34] Session — Focus: A. Lyric Quality

### 1. Dedicated LLM Validation for "Specificity" and "Concreteness"
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/
---


---
## [2026-05-05 01:34] Session — Focus: B. UX & Workflow

### 1. Granular Section Regeneration
**Problem:** The `POST /songs/{slug}/draft` route orchestrates a full song draft or a repair loop for *all* failing sections
---


---
## [2026-05-05 02:34] Session — Focus: C. Genre & Music Theory

### 1. Dynamic Chord Progression Generation & Integration
**Problem:** The current system, as seen in `src/songwriter/api/routes/draft.py` and `src/
---


---
## [2026-05-05 03:34] Session — Focus: D. Cost & Speed

### 1. Adaptive LLM Provider Selection for Draft Attempts
**Problem:** The `_ANTHROPIC_TASKS` dictionary in `src/songwriter/api/llm.py` hard
---


---
## [2026-05-05 04:34] Session — Focus: E. Suno Integration

### 1. Dynamic Suno Style Tags from Song Intent
**Problem:** The LLM prompts like `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in
---


---
## [2026-05-05 05:34] Session — Focus: F. Wild Card

### 1. Real-time LLM Stream for Draft Generation
**Problem:** The current lyric generation process, orchestrated by `POST /songs/{slug}/draft`, appears to be a blocking operation until the
---


---
## [2026-05-05 06:35] Session — Focus: A. Lyric Quality

### 1. Dynamic "Burn Words" from World Context
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter/api/routes
---


---
## [2026-05-05 07:35] Session — Focus: B. UX & Workflow

### 1. Real-time Progress Tracking for Draft Generation
**Problem:** The description of the `POST /songs/{slug}/draft` route outlines a multi-step, iterative process (generate, validate, repair loop, final pass). Currently, this seems like a blocking operation where the user waits for a final result, potentially leading to a "black box" feeling or perceived latency during longer generation
---


---
## [2026-05-05 08:35] Session — Focus: D. Cost & Speed

### 1. Dynamic Output Token Limits for Targeted Repairs
**Problem:** The `TASK_MAX_TOKENS` dictionary in `src/songwriter/api/llm.py` sets a fixed
---


---
## [2026-05-05 09:35] Session — Focus: E. Suno Integration

### 1. Explicit Suno Style Tag and Instrumentation Generation
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py`
---


---
## [2026-05-05 10:35] Session — Focus: F. Wild Card

### 1. LLM-driven Self-Correction and Holistic Critique
**Problem:** The current repair loop, described in `src/songwriter/api/routes/draft.py` (steps
---


---
## [2026-05-05 11:35] Session — Focus: A. Lyric Quality

### 1. Rhyme Quality Enhancement with Dynamic Constraint Generation
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter/
---


---
## [2026-05-05 13:27] Session — Focus: B. UX & Workflow

### 1. User-Initiated Section Locking
**Problem:** The current `POST /songs/{slug}/draft` route orchestrates a repair loop that automatically targets "failing sections
---


---
## [2026-05-05 14:33] Session — Focus: C. Genre & Music Theory

### 1. Granular Cadence Pattern Management & Expansion
**Problem:** The `_GENRE_CADENCES` dictionary in `src/songwriter/api/routes/draft_
---


---
## [2026-05-05 15:33] Session — Focus: A. Lyric Quality

### 1. Incremental Section Generation with Context
**Problem:** The `POST /songs/{slug}/draft` route states: "1. Generate all target sections in one call". This requires
---


---
## [2026-05-05 16:33] Session — Focus: C. Genre & Music Theory

### 1. Dynamic Cadence Pattern Blending for Hybrid Styles
**Problem:** The `_GENRE_CADENCES` dictionary in `src/songwriter/api/routes/
---


---
## [2026-05-05 17:34] Session — Focus: D. Cost & Speed

### 1. Contextual Prompt Truncation for Repair Calls
**Problem:** The `_REPAIR_PROMPT` in `src/songwriter/api/routes/draft.py` includes
---


---
## [2026-05-05 18:50] Session — Focus: E. Suno Integration

### 1. Suno-Specific Burn List for Style Tags
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter/api
---


---
## [2026-05-06 08:18] Session — Focus: F. Wild Card

### 1. Extensible Plugin System for Custom Validation and Repair Logic
**Problem:** The current lyric generation and repair loop, driven by `POST /songs/{slug}/draft`, utilizes a fixed
---


---
## [2026-05-06 12:43] Session — Focus: A. Lyric Quality

### 1. Dynamic "Genre Craft" Rules based on Sub-Genre or Lyrical Style
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in
---


---
## [2026-05-06 13:43] Session — Focus: B. UX & Workflow

### 1. Granular Section Re-drafting on Demand
**Problem:** The `POST /songs/{slug}/draft` route orchestrates a complete song generation or a repair loop that *only
---


---
## [2026-05-06 17:55] Session — Focus: B. UX & Workflow

### 1. Real-time Progress Stream for Draft Generation
**Problem:** The `POST /songs/{slug}/draft` route orchestrates a multi-step process (generate, validate, repair up
---


---
## [2026-05-06 18:55] Session — Focus: D. Cost & Speed

### 1. Adaptive `MAX_ATTEMPTS` for Repair Loop
**Problem:** The `MAX_ATTEMPTS = 2` constant in `src/songwriter/api/routes/
---


---
## [2026-05-06 19:55] Session — Focus: C. Genre & Music Theory

### 1. Chord Progression Integration for Enhanced Musicality
**Problem:** The `_INITIAL_PROMPT` and `_SYSTEM_PROMPT` explicitly state that genre defines "BEAT
---


---
## [2026-05-06 20:55] Session — Focus: E. Suno Integration

### 1. Dynamic Suno Style Tags and Instrumentation Hints in Initial Draft
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py
---


---
## [2026-05-06 21:55] Session — Focus: F. Wild Card

### 1. External Data Integration for World Building (Knowledge Graph / Wiki)
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/
---


---
## [2026-05-06 23:26] Session — Focus: A. Lyric Quality

### 1. Rhyme Quality Scoring and Targeted Repair Prompting
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py` instructs the
---


---
## [2026-05-07 00:26] Session — Focus: B. UX & Workflow

### 1. Section Locking to Preserve Manual Edits
**Problem:** The current `POST /songs/{slug}/draft` route states "1. Generate all target sections in one call
---


---
## [2026-05-07 01:26] Session — Focus: A. Lyric Quality

### 1. Dynamic System Prompting with Contextual Directives
**Problem:** The `_SYSTEM_PROMPT` in `src/songwriter/api/llm.py` is a static,
---


---
## [2026-05-07 02:27] Session — Focus: C. Genre & Music Theory

### 1. Granular Cadence Pattern Editor and Management
**Problem:** The `_GENRE_CADENCES` dictionary in `src/songwriter/api/routes/draft_defaults.
---


---
## [2026-05-07 03:27] Session — Focus: C. Genre & Music Theory

### 1. Dynamic Cadence Pattern Refinement by Song Intent
**Problem:** The `_GENRE_CADENCES` in `src/songwriter/api/routes/draft
---


---
## [2026-05-07 04:27] Session — Focus: D. Cost & Speed

### 1. Dynamic Prompt Compression based on Iteration Progress
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter/
---


---
## [2026-05-07 05:27] Session — Focus: E. Suno Integration

### 1. Generate BPM and Key Signature Metadata with Initial Draft
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py` focuses exclusively
---


---
## [2026-05-07 06:27] Session — Focus: F. Wild Card

### 1. Version Control and History for Song Drafts
**Problem:** The current `POST /songs/{slug}/draft` route implies a destructive update flow, where calling `write_song`
---


---
## [2026-05-07 07:27] Session — Focus: A. Lyric Quality

### 1. Enhanced Lexical Constraint Management (Burn Words / Anchor Words)
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` contain `{burn_words
---


---
## [2026-05-07 08:28] Session — Focus: B. UX & Workflow

### 1. Targeted Single-Section Regeneration
**Problem:** The `POST /songs/{slug}/draft` route's description, "1. Generate all target sections in one call," implies
---


---
## [2026-05-07 09:34] Session — Focus: B. UX & Workflow

### 1. Interactive Micro-Edit (Line-Level LLM Refinement)
**Problem:** The current `POST /songs/{slug}/draft` route primarily operates at the section level,
---


---
## [2026-05-07 11:07] Session — Focus: D. Cost & Speed

### 1. Contextual Truncation and Summarization for `_REPAIR_PROMPT`
**Problem:** The `_REPAIR_PROMPT` in `src/songwriter/
---


---
## [2026-05-07 12:22] Session — Focus: C. Genre & Music Theory

### 1. Dynamic Chord Progression Suggestions based on Genre & Emotion
**Problem:** The system leverages `cadence_patterns` (like `corpus-rap-verse` in `src/
---


---
## [2026-05-07 13:22] Session — Focus: E. Suno Integration

### 1. Dynamic Suno-Ready Style Prompt Generation
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py` and the
---


---
## [2026-05-07 14:23] Session — Focus: F. Wild Card

### 1. AI-Powered Performance Feedback and Vocal Phrasing Suggestions
**Problem:** The `validate_song` function in `src/songwriter/api/validation/orchestrator.py`
---


---
## [2026-05-07 15:23] Session — Focus: A. Lyric Quality

### 1. Granular Scoring and Prioritization for Repair Iterations
**Problem:** The `POST /songs/{slug}/draft` route's loop states, "Keep the best scoring candidate," but
---


---
## [2026-05-07 16:23] Session — Focus: A. Lyric Quality

### 1. Granular Story Arc Guidance for Section Generation
**Problem:** The `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft.py` generates
---


---
## [2026-05-07 17:35] Session — Focus: B. UX & Workflow

### 1. User-Controlled Section Locking for Immutable Content
**Problem:** The current `POST /songs/{slug}/draft` route, as described by "1. Generate all target sections in
---


---
## [2026-05-07 18:54] Session — Focus: C. Genre & Music Theory

### 1. Enhanced Sub-Genre Specific Lyrical Craft Guidance in Prompts
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `
---


---
## [2026-05-07 19:54] Session — Focus: D. Cost & Speed

### 1. Early Exit for Repair Loop Based on Validation Score
**Problem:** The `POST /songs/{slug}/draft` route states, "Repeat up to max_attempts. Keep
---


---
## [2026-05-07 20:54] Session — Focus: E. Suno Integration

### 1. Injecting Suno-Specific Arrangement & Instrumentation Tags
**Problem:** The lyrics generated by the `_INITIAL_PROMPT` in `src/songwriter/api/routes/draft
---


---
## [2026-05-07 21:55] Session — Focus: F. Wild Card

### 1. Song Draft Version Control
**Problem:** The current workflow implied by `POST /songs/{slug}/draft` and the use of `write_song` in `src/songwriter
---


---
## [2026-05-07 22:55] Session — Focus: A. Lyric Quality

### 1. Dynamic Negative Constraints from Repeated LLM Failures
**Problem:** The `_INITIAL_PROMPT` and `_REPAIR_PROMPT` in `src/songwriter/
---

