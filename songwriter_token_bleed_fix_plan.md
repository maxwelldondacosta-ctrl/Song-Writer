# Songwriter App — Token Bleed Diagnosis + Fix Plan

## Situation

Cerebras has solved the speed problem.

Generation speed has improved from roughly:

```text
5 minutes → 4–5 seconds
```

That is a massive product improvement.

The remaining issue is token usage. The app is likely haemorrhaging tokens because of prompt structure, repeated context, over-wide output limits, and validation/correction loops.

The problem is probably not Cerebras itself. It is likely that the app is feeding the model too much context and asking for too much output.

---

# 1. Likely Causes of Token Haemorrhage

## 1.1 Full song spec is being sent every call

If every small task includes the full project instructions, the app is wasting tokens.

Bad pattern:

```text
full style guide
full scoring system
full phonetic rules
full cadence rules
full examples
full previous lyrics
full burn list
full validation notes
```

For a small task like line alternatives, this is excessive.

## Better approach

Split prompts by task.

| Task | Should Include |
|---|---|
| Full song draft | Full brief + structure + key rules |
| Rewrite one line | Target line + 2 nearby context lines + specific rule |
| Generate alternatives | Target line + short style summary |
| Validate cadence | Lyrics only + cadence rule |
| Suno prompt | Song summary + genre + vocal/production notes |

Do not send the whole songwriting rulebook for a tiny rewrite request.

---

## 1.2 The model is outputting explanations you do not need

If prompts use words like:

```text
analyse
improve
explain
score
critique
```

the model may output:

```text
reasoning
notes
breakdowns
why this works
suggestions
commentary
```

For app execution, that is token waste.

## Fix

For generation tasks, require compact structured output:

```text
Return ONLY JSON.
No explanation.
No notes.
No markdown.
No analysis.
```

Example alternatives output:

```json
{
  "alternatives": [
    "line one",
    "line two",
    "line three"
  ]
}
```

No commentary. No “Here are some options.”

---

## 1.3 Correction loop may be resending the full draft

If one line fails validation, the app may be sending the entire song back for repair.

Bad pattern:

```text
Here is the whole song.
Here are all validator errors.
Rewrite the full song.
```

That burns tokens and risks damaging good lines.

## Better approach

Repair only failed lines.

Use a patch format:

```json
{
  "replacements": [
    {
      "section_id": "verse_1",
      "line_index": 3,
      "old": "I fall through the shadows",
      "new": "I sink where the streetlights die"
    }
  ]
}
```

The app should apply patches locally.

---

## 1.4 The app may be generating full sections when line-level changes are enough

A songwriting app should separate task types clearly.

Recommended task types:

```text
DRAFT_FULL_SONG
REWRITE_SECTION
REWRITE_LINE
GENERATE_LINE_ALTERNATIVES
REPAIR_FAILED_LINES
FORMAT_FOR_SUNO
GENERATE_SUNO_PROMPT
TITLE_IDEAS
```

Do not use one mega “songwriter agent” prompt for every job.

---

## 1.5 `max_tokens` may be too high globally

If every call uses a large output cap, the model has permission to ramble.

Bad:

```python
max_tokens = 4000
```

for every task.

## Fix

Set output caps by task.

```python
MAX_OUTPUT_TOKENS = {
    "DRAFT_FULL_SONG": 1800,
    "REWRITE_SECTION": 700,
    "REWRITE_LINE": 120,
    "LINE_ALTERNATIVES": 250,
    "VALIDATE_SECTION": 400,
    "REPAIR_FAILED_LINES": 500,
    "SUNO_PROMPT": 250,
    "TITLE_IDEAS": 150,
}
```

For Suno prompts, keep output especially tight:

```text
max_output_tokens: 250
```

Suno prompts usually need to stay under 1000 characters anyway.

---

## 1.6 Validators may be calling the LLM too often

If deterministic validators and LLM validators are both running, check whether every section triggers a separate LLM call.

Bad pattern:

```python
for section in sections:
    call_llm_story_validation(section)
```

For an 8-section song, that becomes 8 extra LLM calls.

## Better approach

Run deterministic validators first.

Only call the LLM validator if:

```text
the deterministic score is borderline
the user requests deep critique
the issue requires semantic judgement
```

Or batch the validation:

```text
Validate all sections in one call, return compact JSON.
```

Example:

```json
{
  "issues": [
    {
      "section": "verse_1",
      "line": 4,
      "issue": "weak image"
    },
    {
      "section": "hook",
      "line": 2,
      "issue": "generic phrase"
    }
  ]
}
```

---

# 2. Fast Fixes to Make Immediately

## 2.1 Add token logging by task

You need to see exactly where the bleed is happening.

Log each LLM call like:

```text
[llm] task=DRAFT_FULL_SONG in=8420 out=1960 cost=$0.0062 latency=4.8s
[llm] task=LINE_ALTERNATIVES in=6100 out=900 cost=$0.0031 latency=2.1s
```

If `LINE_ALTERNATIVES` has 6K input tokens, that is the crime scene.

---

## 2.2 Add prompt length print before each call

Simple estimate:

```python
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
```

Before calling the LLM:

```python
print(
    f"[prompt] task={task_type} "
    f"chars={len(prompt)} "
    f"est_tokens={estimate_tokens(prompt)}"
)
```

This is crude but useful.

---

## 2.3 Create mini prompts for small tasks

Example line alternative prompt:

```text
You are rewriting one lyric line.

Style:
{brief_style_summary}

Original line:
{line}

Nearby context:
{previous_line}
{next_line}

Rules:
- Keep meaning close
- Max 7 syllables
- Return 5 alternatives
- Return ONLY JSON

Schema:
{"alternatives":["..."]}
```

This should be hundreds of tokens, not thousands.

---

## 2.4 Return patches instead of full lyrics

For corrections, return only what changed.

```json
{
  "patches": [
    {
      "section": "hook",
      "line": 2,
      "new": "Burn my name in gold"
    }
  ]
}
```

The app applies the patch locally.

This cuts output tokens and protects already-good lyrics.

---

# 3. Ideal Token Budget by Task

| Task | Input Target | Output Target |
|---|---:|---:|
| Full song draft | 2K–5K | 800–1800 |
| Section rewrite | 1K–2K | 300–700 |
| Line alternatives | 300–900 | 100–250 |
| Failed-line repair | 800–1500 | 150–500 |
| Validation summary | 1K–3K | 200–600 |
| Suno prompt | 500–1200 | 100–250 |
| Title ideas | 200–700 | 50–150 |

If small tasks are using 5K–8K input tokens, the prompt design is the problem.

---

# 4. Use a Compact Song Style Card

Instead of sending the full project spec every time, create a short reusable style card.

Example:

```text
STYLE CARD:
Genre: Dark fantasy indie rock
Vocal: aggressive male, gritty, cinematic
Line length: max 7 syllables unless chorus lift
Imagery: blood, crowns, ash, hunger, throne, demon, iron
Avoid: generic pain/lost/shadow unless specific
Structure: labelled Suno sections
Tone: brutal, mythic, not poetic fluff
```

Use this card for small tasks like:

```text
line alternatives
line repair
title ideas
Suno prompt
hook variations
```

Only use the full brief for full-song drafts or major section rewrites.

---

# 5. Recommended Task Design

## 5.1 Full song draft

Use when creating a complete first version.

Include:

```text
full brief
genre
story arc
structure
syllable rules
style rules
rhyme/cadence target
section labels
```

Output:

```json
{
  "sections": [
    {
      "id": "verse_1",
      "label": "Verse 1",
      "lyrics": [
        "Line one",
        "Line two"
      ]
    }
  ]
}
```

---

## 5.2 Rewrite section

Use when a whole verse/hook is weak.

Include:

```text
style card
section lyrics
specific issues
target line count
syllable rule
```

Output only the rewritten section:

```json
{
  "section_id": "verse_1",
  "lyrics": [
    "New line one",
    "New line two"
  ]
}
```

---

## 5.3 Rewrite line

Use for precise fixing.

Include:

```text
style card
target line
previous line
next line
problem to fix
```

Output:

```json
{
  "new_line": "Replacement line"
}
```

---

## 5.4 Generate line alternatives

Use for options.

Include:

```text
style card
target line
nearby context
number of alternatives
```

Output:

```json
{
  "alternatives": [
    "Option one",
    "Option two",
    "Option three",
    "Option four",
    "Option five"
  ]
}
```

---

## 5.5 Repair failed lines

Use after deterministic validation.

Include only:

```text
style card
failed lines
validator errors
nearby context for each failed line
```

Output patch format:

```json
{
  "patches": [
    {
      "section_id": "verse_1",
      "line_index": 3,
      "old": "Old line",
      "new": "New line"
    }
  ]
}
```

---

## 5.6 Generate Suno prompt

Include:

```text
song genre
vocal style
tempo/energy
instrumentation
mood
structure
production notes
```

Output:

```json
{
  "prompt": "Dark fantasy indie rock, aggressive male vocal..."
}
```

Keep under 1000 characters.

---

# 6. Correction Loop Design

## Bad loop

```text
Generate full song
Validate
Rewrite full song
Validate
Rewrite full song again
```

This is expensive and destructive.

## Better loop

```text
Generate full song
Run deterministic validators
Identify failed lines/sections
Repair only failed lines or failed sections
Apply patches locally
Revalidate changed parts
Stop after 2 attempts
```

Recommended default:

```python
MAX_ATTEMPTS = 2
```

Premium mode:

```python
MAX_ATTEMPTS = 3
```

---

# 7. Suggested Logging Fields

Each LLM call should log:

```json
{
  "task_type": "LINE_ALTERNATIVES",
  "provider": "cerebras",
  "model": "qwen3-235b",
  "input_chars": 2400,
  "input_tokens_est": 600,
  "output_chars": 800,
  "output_tokens_est": 200,
  "max_tokens": 250,
  "latency_s": 1.1,
  "estimated_cost": 0.001,
  "repair_attempt": false,
  "json_ok": true,
  "schema_ok": true
}
```

Track this per generation:

```text
total calls
total input tokens
total output tokens
total estimated cost
slowest task
largest prompt
largest output
repair count
```

---

# 8. Immediate Debugging Checklist

Run one full song generation and inspect:

```text
1. How many LLM calls happen?
2. Which task uses the most input tokens?
3. Which task uses the most output tokens?
4. Are validators calling the LLM per section?
5. Are small tasks receiving the full song spec?
6. Is max_tokens globally too high?
7. Are correction passes rewriting full sections or whole songs?
8. Is the model returning explanations?
9. Are burn-list repairs done by LLM or regex?
10. Are failed lines repaired as patches?
```

The top three token-heavy calls are where the fix should start.

---

# 9. Clean Diagnosis

The speed problem is solved.

The new problem is probably:

```text
too much prompt context
too much full-song rewriting
too many validation calls
too much explanatory output
max_tokens too high everywhere
no patch-based repair
```

The app is likely feeding Cerebras like a medieval banquet and acting shocked when the bill arrives.

---

# 10. Immediate Next Move

Add logging for:

```text
task_type
input token estimate
output token estimate
max_tokens
latency
repair_attempt
call_count_per_generation
```

Then run one generation and identify the top three token-heavy calls.

Do this before changing models again.

The model is no longer the bottleneck. The app’s prompt and repair design are.
