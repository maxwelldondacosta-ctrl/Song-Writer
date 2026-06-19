from songwriter.api.llm import LLMError, ask_llm_json as ask_claude_json
from songwriter.api.settings import get_settings
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
        payload = ask_claude_json(prompt, task="VALIDATE")
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
