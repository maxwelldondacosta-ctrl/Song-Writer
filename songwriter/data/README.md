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
