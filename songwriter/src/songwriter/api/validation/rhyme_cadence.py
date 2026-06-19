from collections import Counter

from songwriter.api.validation import RuleOutcome, ValidationContext
from songwriter.api.validation.tokenizer import WordToken


def check_section(line_tokens: list[list[WordToken]], ctx: ValidationContext) -> RuleOutcome:
    if ctx.cadence_pattern is None:
        return RuleOutcome("warn", ["no cadence pattern"])
    end_classes: list[str] = []
    for line in line_tokens:
        last = next((t for t in reversed(line) if not t.unknown and t.rhyme_class), None)
        if last:
            end_classes.append(last.rhyme_class)
    if len(end_classes) < 2:
        return RuleOutcome("warn", ["section has fewer than 2 line endings with phonetic data"])
    common = Counter(end_classes).most_common(1)[0]
    if common[1] >= 2:
        # at least one rhyme pair → check perfect-rhyme allowed
        if "perfect" in (ctx.cadence_pattern.rhyme_compatibility.get("end") or []):
            return RuleOutcome("pass", [])
        return RuleOutcome("warn", [f"rhyme pair on '{common[0]}' but cadence allows {ctx.cadence_pattern.rhyme_compatibility}"])
    return RuleOutcome("warn", ["no rhyme pair detected across line endings"])
