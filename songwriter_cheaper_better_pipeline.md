# Songwriter App — Cheaper, Better Pipeline

## Core Point

The current app is probably doing the expensive version of the wrong thing:

```text
Big prompt + full database + full song generation + broad validation + broad rewrite
```

That burns tokens and still produces weak lyrics because the model is drowning in instructions.

The better approach is:

```text
Use the database as a selector, not as prompt stuffing.
```

Your app should decide the song structure, pattern, cadence, imagery, and constraints before the LLM writes anything.

The LLM should only generate language inside a tight creative box.

---

# 1. Why the Current Approach Produces Slop

## Problem

If the model receives:

```text
full pattern database
full word bank
full style guide
full scoring system
full phonetic analysis
full examples
full validator notes
full brief
```

then it does not pick the sharpest idea.

It averages everything.

That creates:

```text
generic competent mush
dark fantasy fridge magnet lyrics
pretty but empty lines
overused words
weak story progression
```

More analysis does not automatically create better songwriting.

The model needs fewer, sharper constraints.

---

# 2. Better Model

Use the pattern/database engine before generation.

## Database/pattern engine selects:

```text
1 song engine
1 structure pattern
1 cadence pattern
1 imagery palette
1 rhyme behaviour
5–10 banned cliché moves
```

Then the LLM only receives those selected constraints.

## Example selected constraints

```json
{
  "song_engine": "fall-from-hero transformation",
  "structure_pattern": "8-line narrative verse + 4-line repeated hook",
  "cadence_pattern": "short punch lines, max 7 syllables",
  "rhyme_behaviour": "loose couplets with internal echoes",
  "imagery_palette": [
    "rusted crown",
    "ash rain",
    "split altar",
    "black throne",
    "bone gate"
  ],
  "forbidden_moves": [
    "generic darkness",
    "heart/pain/soul clichés",
    "empty mirror lines",
    "abstract sadness",
    "random blood/fire/demon words with no action"
  ]
}
```

Only feed those into the prompt.

Do not feed the whole database.

---

# 3. Cost Difference

## Current likely flow

```text
Full song prompt: 8K–15K input tokens
Full output: 1.5K–3K output tokens
Validation: multiple full-section calls
Correction: rewrites full sections or whole song
```

This can easily become:

```text
20K–50K tokens per song
```

That is expensive and still not reliable.

## Better flow

```text
Selector: local logic or tiny prompt
Section draft: 800–1.5K input, 300–600 output
Line repair: 300–900 input, 50–200 output
Suno format: 500–1000 input, 100–200 output
```

More realistic total:

```text
5K–15K tokens per song
```

The output should also be better because each section has a specific job.

---

# 4. Correct Division of Labour

This should work like the RPG architecture.

## RPG

```text
Server owns mechanics.
Model owns prose.
```

## Songwriter

```text
App owns song architecture.
Model owns lyric lines.
```

Your app should control:

```text
song engine
section jobs
structure
rhyme/cadence constraints
imagery palette
banned clichés
validation
repair targeting
Suno formatting
```

The model should handle:

```text
generating lines inside the box
creating alternatives
repairing failed lines
tightening specific sections
```

Do not make the model be:

```text
database
analyst
poet
critic
editor
producer
all at once
```

That creates slop.

---

# 5. Recommended Pipeline

## Step 1 — Concept intake

User gives the idea.

Example:

```text
A dark fantasy indie rock song where a hero kills the demon king but becomes the new demon king.
```

---

## Step 2 — Select one song engine

The app chooses the central engine.

Examples:

```text
fall-from-hero transformation
revenge confession
toxic love autopsy
seduction as power game
spiritual corruption arc
regret after betrayal
```

Example output:

```json
{
  "song_engine": "fall-from-hero transformation",
  "central_turn": "the hero defeats the demon king, then becomes him",
  "emotional_target": "triumph turning into horror",
  "final_line_function": "reveal the transformation"
}
```

---

## Step 3 — Select one structure pattern

Example:

```json
{
  "structure": [
    {
      "section": "Verse 1",
      "job": "arrival in the new world and first violence",
      "line_count": 8
    },
    {
      "section": "Chorus",
      "job": "state the brutal survival thesis",
      "line_count": 4
    },
    {
      "section": "Verse 2",
      "job": "rise through battles and power",
      "line_count": 8
    },
    {
      "section": "Bridge",
      "job": "face the demon king and realise the cost",
      "line_count": 4
    },
    {
      "section": "Final Chorus",
      "job": "reveal the hero has become the new demon king",
      "line_count": 4
    }
  ]
}
```

---

## Step 4 — Select imagery palette

Keep this small.

Example:

```json
{
  "imagery_palette": [
    "ash rain",
    "rusted crown",
    "bone gate",
    "split altar",
    "black throne"
  ]
}
```

Rules:

```text
Use images only where they serve the section job.
Do not sprinkle all images randomly.
Every image must describe action, consequence, or transformation.
```

---

## Step 5 — Generate section-by-section

Do not ask for the full song unless it is only a rough draft.

Better:

```text
Write Verse 1 only.
```

Prompt example:

```text
Write Verse 1.

Section job:
The protagonist wakes in a strange world, kills his first monster, and realises survival will change him.

Constraints:
- 8 lines
- max 7 syllables per line
- physical imagery over abstract emotion
- loose couplet rhyme
- no "darkness", "pain", "soul", "broken"
- do not mention the demon king yet
- every line must move the story forward
- return JSON only

Schema:
{
  "section_id": "verse_1",
  "lyrics": ["line 1", "line 2"]
}
```

This is cheaper and much harder for the model to ruin.

---

# 6. Line-Level Validation

Each generated line should be scored individually.

## Line pass checks

```text
Does it say something new?
Can I picture it?
Does it fit the section job?
Does it avoid cliché?
Does it sing?
Does it stay under the syllable limit?
Does it create forward motion?
```

If a line fails, repair that line only.

Do not rewrite the whole section unless the whole section fails.

---

# 7. Repair Failed Lines Only

## Bad repair prompt

```text
This verse has issues. Rewrite the whole thing.
```

That wastes tokens and destroys good lines.

## Better repair prompt

```text
This line failed because it is generic:
"{line}"

Section job:
{section_job}

Nearby context:
Previous line: {previous_line}
Next line: {next_line}

Replace it with 5 options.

Rules:
- max 7 syllables
- must show a physical action or object
- must advance the story
- no generic emotion words
- no decorative dark words
- keep the same rhyme sound if possible
- return JSON only

Schema:
{
  "alternatives": ["option 1", "option 2"]
}
```

Then choose the best alternative locally.

---

# 8. Patch-Based Correction

For failed-line repair, return patches.

```json
{
  "patches": [
    {
      "section_id": "verse_1",
      "line_index": 3,
      "old": "I fall through the shadows",
      "new": "I crawl through ash rain"
    }
  ]
}
```

The app applies the patch.

This prevents the model from rewriting good lines for no reason.

---

# 9. Anti-Slop Rule

Add this rule to generation and repair prompts:

```text
If a line could fit 100 other songs, it fails.
```

This is one of the strongest anti-generic rules.

## Weak line

```text
Blood on my crown in the fire of sin
```

Problem:

```text
generic dark words
no specific action
could fit hundreds of songs
```

## Better line

```text
I wore the crown till it cut my skin
```

Why it works:

```text
specific image
physical action
implied consequence
clearer emotional meaning
```

---

# 10. Word Banks Should Not Be Used as Decoration

A word bank can help, but it cannot write the song.

Words like:

```text
ash
blood
crown
sin
grave
fire
throne
knife
angel
demon
```

are not automatically good.

They become weak when sprinkled randomly.

## Bad

```text
Blood on my crown in the fire of sin
```

## Better

```text
The crown cuts blood from me
```

The second line has action.

Rule:

```text
A strong word must be attached to action, object, consequence, or story movement.
```

---

# 11. Use Database as Selector, Not Inspiration Dump

## Bad flow

```text
Prompt includes database insights → model writes using everything
```

Result:

```text
generic blended output
```

## Better flow

```text
Database selects 3–5 constraints → model writes inside those constraints
```

Example selected constraints:

```json
{
  "structure_pattern": "8-line narrative verse + 4-line repeated hook",
  "rhyme_pattern": "AABB with internal echoes",
  "imagery_palette": ["rusted crown", "ash rain", "split altar"],
  "cadence_rule": "short punch lines, max 7 syllables",
  "forbidden_moves": ["generic darkness", "heart/pain/soul clichés"]
}
```

Only those constraints go to the model.

---

# 12. Recommended App Flow

```text
1. User gives concept
2. App selects ONE song engine
3. App selects ONE structure pattern
4. App selects ONE imagery palette
5. App writes section-by-section
6. App validates line-by-line
7. App repairs only failed lines
8. App performs final cohesion pass
9. App formats for Suno
```

The model is not asked to “write a great song.”

It is asked to complete one narrow job at a time.

---

# 13. Example Full Section Prompt

```text
You are writing lyrics for a dark fantasy indie rock song.

You are not writing a poem.
You are writing lyrics that must survive being sung.

Section:
Verse 1

Section job:
The protagonist wakes in a strange world, kills his first monster, and realises survival will change him.

Song engine:
Fall-from-hero transformation.

Central story turn:
The hero defeats the demon king, then becomes him.

Important:
Do not mention the demon king yet.
Do not mention the throne yet.
This verse is only the beginning.

Constraints:
- 8 lines
- max 7 syllables per line
- loose couplet rhyme
- physical imagery over abstract emotion
- every line must move the story forward
- no generic "darkness", "pain", "soul", "broken"
- if a line could fit 100 other songs, it fails

Imagery palette:
ash rain
bone gate
rusted crown

Use only if relevant.

Return ONLY JSON.

Schema:
{
  "section_id": "verse_1",
  "lyrics": [
    "line 1",
    "line 2",
    "line 3",
    "line 4",
    "line 5",
    "line 6",
    "line 7",
    "line 8"
  ]
}
```

---

# 14. Example Line Repair Prompt

```text
Repair one failed lyric line.

Failed line:
"I fall through the shadows"

Failure reason:
Generic image. Could fit 100 other songs. Does not advance the story.

Section:
Verse 1

Section job:
The protagonist wakes in a strange world, kills his first monster, and realises survival will change him.

Nearby context:
Previous line: "Ash rain burns my tongue"
Next line: "Something crawls beneath"

Rules:
- Give 5 alternatives
- max 7 syllables each
- physical image or action required
- must fit the nearby lines
- must advance the story
- no "darkness", "pain", "soul", "broken", "shadow"
- return JSON only

Schema:
{
  "alternatives": [
    "option 1",
    "option 2",
    "option 3",
    "option 4",
    "option 5"
  ]
}
```

---

# 15. Why This Will Be Cheaper

The app stops paying the LLM to think about everything.

## Before

```text
LLM receives:
full database
full instructions
full song
full validation
full rewrite demand
```

## After

```text
LLM receives:
one section job
one small constraint set
one output schema
```

This reduces:

```text
input tokens
output tokens
retry cost
repair cost
rewrite waste
validation overhead
```

It also improves quality because the model has less room to drift.

---

# 16. Best Practical Next Step

Change the app from:

```text
write whole song from giant prompt
```

to:

```text
select constraints → write one section → validate lines → repair failed lines
```

Do this before changing models again.

Cerebras already solved the speed problem.

The remaining issue is control.

The way to get control is not more data.

It is fewer, sharper constraints.
