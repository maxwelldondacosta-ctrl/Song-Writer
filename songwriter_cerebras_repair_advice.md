# Songwriter App — Cerebras Wiring + Repair Advice

## Quick Verdict

The songwriter app is **not broken beyond repair**.

The skeleton is good:

```text
Song object → draft prompt → LLM JSON lyrics → validation engines → correction loop
```

That is the right basic structure.

The strongest part of the app is the deterministic validation layer:

```text
cadence
phonetic texture
rhyme
singability
cohesion
story validation
```

That is exactly the kind of thing the LLM should not be trusted to self-check.

The weak point is the **LLM layer and prompt contract**.

The app still thinks in terms of Claude, even though you are now wiring it to Cerebras. That legacy naming will cause confusion if it is not cleaned up.

---

# 1. Rename `ask_claude()` conceptually

## Problem

The API still exposes functions like:

```python
ask_claude()
ask_claude_json()
```

But internally it may now call:

```text
Cerebras
Anthropic
Claude CLI
```

That is misleading.

## Fix

Rename the main functions conceptually:

```python
ask_llm()
ask_llm_json()
```

Keep backwards compatibility temporarily:

```python
def ask_claude(prompt, **kwargs):
    return ask_llm(prompt, **kwargs)

def ask_claude_json(prompt, **kwargs):
    return ask_llm_json(prompt, **kwargs)
```

This lets old code keep working while the app moves toward a proper provider-neutral LLM layer.

---

# 2. Stop using fake Claude tier labels

## Problem

The app appears to use tier labels like:

```text
sonnet
haiku
```

But those labels may now route to Cerebras or other providers.

That is confusing.

## Fix

Use task labels or model labels instead.

Bad:

```python
draft_tier = "sonnet"
fast_tier = "haiku"
```

Better:

```python
creative_model = "cerebras_qwen3_235b"
fast_model = "cerebras_qwen3_235b"
fallback_model = "cerebras_qwen3_235b"
```

Best:

```python
MODEL_ROUTES = {
    "DRAFT_LYRICS": "cerebras_qwen3_235b",
    "CORRECT_LYRICS": "cerebras_qwen3_235b",
    "LINE_ALTERNATIVES": "cerebras_qwen3_235b",
    "STORY_VALIDATION": "cerebras_qwen3_235b",
    "COHESION_VALIDATION": "cerebras_qwen3_235b",
    "SUNO_PROMPT": "cerebras_qwen3_235b",
    "DESCRIPTOR_REGEN": "cerebras_qwen3_235b",
}
```

Do not call a Cerebras route `"sonnet"`. That is future-bug fuel.

---

# 3. Improve JSON extraction

## Problem

If `ask_claude_json()` only does something like:

```python
candidate = fenced_json if found else raw
json.loads(candidate)
```

then it can fail on common model outputs like:

```text
Here is the JSON:
{...}
```

or multiple fenced blocks, trailing text, or provider-specific formatting.

Cerebras Qwen may behave well most of the time, but “most of the time” is not an architecture.

## Suggested JSON extractor

```python
import json
import re

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

def extract_json(raw: str):
    raw = (raw or "").strip()

    # 1. Fenced JSON first
    match = _JSON_FENCE.search(raw)
    if match:
        return json.loads(match.group(1).strip())

    # 2. Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 3. Fallback: first balanced-looking object or list
    starts = [i for i in [raw.find("{"), raw.find("[")] if i != -1]
    if not starts:
        raise ValueError("No JSON object/list found in LLM output")

    start = min(starts)

    for end in range(len(raw), start, -1):
        chunk = raw[start:end].strip()
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Could not parse JSON from LLM output:\n{raw}")
```

Ugly but useful. Model integration is basically cleaning up after very confident autocomplete.

---

# 4. Add schema validation after JSON parsing

## Problem

Parsing JSON is not enough.

The draft generator expects something like:

```json
{
  "sections": [
    {
      "id": "verse_1",
      "lyrics": ["Line one", "Line two"]
    }
  ]
}
```

Line alternatives expect something like:

```json
{
  "alternatives": ["line one", "line two"]
}
```

The app should validate shape before using the result.

## Draft payload validator

```python
def validate_draft_payload(payload: dict) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload is not an object"

    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        return False, "missing or empty sections list"

    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            return False, f"section {idx} is not an object"

        if not isinstance(section.get("id"), str) or not section["id"].strip():
            return False, f"section {idx} missing id"

        lyrics = section.get("lyrics")
        if not isinstance(lyrics, list):
            return False, f"section {idx} lyrics missing or not list"

        if not all(isinstance(line, str) and line.strip() for line in lyrics):
            return False, f"section {idx} lyrics must be non-empty strings"

    return True, ""
```

## Alternatives payload validator

```python
def validate_alternatives_payload(payload: dict) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload is not an object"

    alternatives = payload.get("alternatives")
    if not isinstance(alternatives, list) or not alternatives:
        return False, "missing or empty alternatives list"

    if not all(isinstance(x, str) and x.strip() for x in alternatives):
        return False, "alternatives must be non-empty strings"

    return True, ""
```

---

# 5. Add repair-once logic

## Problem

If the model returns invalid JSON or the wrong schema, the app should not just crash or accept bad output.

## Fix

Use a repair pass once.

```python
def repair_json_prompt(bad_output: str, error: str, schema_description: str) -> str:
    return f'''
Your previous response failed validation.

Return ONLY corrected JSON.
No prose.
No markdown.
No explanation.

Validation error:
{error}

Required schema:
{schema_description}

Bad output:
{bad_output}
'''.strip()
```

Pipeline:

```text
Call model
Extract JSON
Validate schema
If invalid: repair once
If repair fails: return clean error
```

Do not loop forever. That is how apps become invoice machines.

---

# 6. Increase `MAX_ATTEMPTS`

## Problem

If the draft loop has:

```python
MAX_ATTEMPTS = 1
```

then the correction engine is basically disabled.

The app becomes:

```text
Generate once → validate → shrug
```

That wastes the whole validation system.

## Recommendation

Default:

```python
MAX_ATTEMPTS = 2
```

Premium mode:

```python
MAX_ATTEMPTS = 3
```

Avoid very high defaults. Too many LLM passes become slow and expensive.

---

# 7. Do not silently scrub burn-list words

## Problem

If `_scrub()` silently replaces forbidden/burn-list words, it can damage:

```text
meaning
rhyme
metre
cadence
emotional punch
```

Example:

```text
Original: I fall through the shadows
Scrubbed: I fall through the [random substitute]
```

The replacement might satisfy a word filter but break the song.

## Better behaviour

In validation mode:

```text
flag burn words
show line numbers
suggest alternatives
do not rewrite silently
```

In auto-fix mode:

```text
send the line back to the LLM with specific repair instructions
preserve meaning
preserve syllable count
preserve rhyme if possible
```

Recommended metric:

```text
burn_word_hits
```

---

# 8. Make concrete imagery a preference, not a hard ban

## Problem

The prompt says something like:

```text
Concrete imagery only — name the object, place, or action. No abstract emotion words.
```

That is good for fighting AI slop, but too strict for songwriting.

Songs sometimes need direct emotional words, especially in hooks.

## Better prompt wording

```text
Prefer concrete imagery over abstract emotion.

Abstract emotion words are allowed only when they sharpen the hook, reveal a turn, or land the central feeling.

Avoid generic filler like:
pain
broken
shadows
empty
lost
darkness
unless made specific through image, action, or context.
```

This keeps pressure against cliché without strangling the song.

---

# 9. Cap parallel validation workers

## Problem

If `validate_song()` uses something like:

```python
ThreadPoolExecutor(max_workers=len(llm_sections))
```

then a 10-section song can trigger 10 simultaneous LLM calls.

That can hit provider rate limits or spike latency/cost.

## Fix

Cap workers:

```python
max_workers = min(4, len(llm_sections))
```

Or make it configurable:

```python
llm_validation_workers: int = 4
```

---

# 10. Add cost and latency logging

## Problem

The app may log elapsed time and character count, but should also log rough token/cost estimates.

## Simple token estimate

```python
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
```

## Example log

```text
[llm] task=DRAFT_LYRICS provider=cerebras model=qwen3-235b 1.2s in≈3200 out≈900 cost≈$0.003 ok=true
```

Track:

```text
task type
provider
model
latency
input token estimate
output token estimate
estimated cost
json ok
schema ok
repair used
```

This helps compare Cerebras against future Sonnet/Opus polishing.

---

# 11. Recommended Cerebras wiring

## Settings

Use clear provider/model settings.

```python
class Settings(BaseSettings):
    cerebras_model_id: str = "qwen-3-235b-a22b-instruct-2507"
    cerebras_key_path: str = "~/.cerebras_api_key"

    default_llm_provider: str = "cerebras"
    default_llm_model: str = "qwen3_235b"

    llm_timeout_s: int = 60
    llm_validation_workers: int = 4
```

Adjust model ID to match the actual Cerebras API identifier.

## Public functions

```python
def ask_llm(
    prompt: str,
    *,
    task_type: str = "GENERAL",
    settings: Settings | None = None
) -> str:
    ...

def ask_llm_json(
    prompt: str,
    *,
    task_type: str = "GENERAL",
    settings: Settings | None = None
) -> dict:
    ...
```

Compatibility aliases:

```python
ask_claude = ask_llm
ask_claude_json = ask_llm_json
```

---

# 12. Recommended task route map

For now, keep it simple.

```python
TASK_ROUTES = {
    "DRAFT_LYRICS": "cerebras_qwen3_235b",
    "CORRECT_LYRICS": "cerebras_qwen3_235b",
    "LINE_ALTERNATIVES": "cerebras_qwen3_235b",
    "STORY_VALIDATION": "cerebras_qwen3_235b",
    "COHESION_VALIDATION": "cerebras_qwen3_235b",
    "SUNO_PROMPT": "cerebras_qwen3_235b",
    "DESCRIPTOR_REGEN": "cerebras_qwen3_235b",
}
```

Do not build a complicated MaxRPG-style router yet unless you actually need it.

The songwriter needs:

```text
one fast reliable model
strong JSON extraction
schema validation
repair once
good prompt contracts
limited retry loop
```

Not a 7-provider cathedral of needless misery.

---

# 13. Where Cerebras is a good fit

Cerebras Qwen is likely strong for:

```text
fast drafts
line alternatives
hook variations
Suno prompt generation
JSON outputs
formatting
quick repair passes
```

It may be weaker than Sonnet/Opus for:

```text
elite emotional nuance
high-end metaphor shaping
final lyric polish
very delicate voice preservation
```

But for building the app and making it responsive, Cerebras is the right default to test first.

---

# 14. Future premium mode

Later, add a premium model option:

```text
Premium Polish → Claude Sonnet / Opus or another high-creativity model
```

Use it only for:

```text
final rewrite
hook improvement
rhyme elevation
emotional sharpening
commercial polish
```

Do not use premium models for every draft unless the app enjoys burning money like a tiny record label with no accountant.

---

# 15. Preserve-wording mode

For your own workflow, add a mode that prevents the model from rewriting too aggressively.

Suggested modes:

```text
Analyse only
Score brutally
Suggest fixes only
Rewrite selected line
Tighten syllables without changing meaning
Generate hook alternatives
Generate verse in same style
Format for Suno
Create Suno prompt under 1000 characters
```

This prevents the usual model crime:

```text
User asks for tightening.
Model rewrites the whole song into polished oatmeal.
```

---

# 16. Priority Fix List

## Do first

```text
1. Rename ask_claude mentally/code-wise to ask_llm.
2. Make Cerebras the default route.
3. Improve JSON extraction.
4. Add validators for draft and alternatives payloads.
5. Add repair-once logic for invalid JSON/schema.
6. Cap validation ThreadPoolExecutor workers.
```

## Do next

```text
7. Change MAX_ATTEMPTS default from 1 to 2.
8. Stop silently regex-scrubbing burn words.
9. Add task_type to LLM calls.
10. Add cost/latency logging.
11. Adjust prompt wording so concrete imagery is preferred, not absolute.
```

## Later

```text
12. Add model comparison mode: Cerebras vs Sonnet on same prompt.
13. Add lyric scoring profile presets: brutal, commercial, poetic, Suno-ready.
14. Add selected-line rewrite instead of full-section rewrite.
15. Add preserve-wording mode for user lyrics.
16. Add premium polish route.
```

---

# Final Recommendation

Wire Cerebras in first.

Do not overbuild the provider architecture yet.

The app’s biggest weakness is not model intelligence. It is contract enforcement:

```text
JSON extraction
schema validation
repair once
limited retry loop
non-destructive lyric validation
clear prompt contracts
```

Once those are fixed, Cerebras Qwen should be good enough for a fast songwriting workflow.

Later, add a premium polish model if you want higher-end lyrical taste.
