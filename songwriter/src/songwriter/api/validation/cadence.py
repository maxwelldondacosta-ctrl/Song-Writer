from songwriter.api.validation import RuleOutcome, ValidationContext
from songwriter.api.validation.tokenizer import WordToken


def _line_stress(tokens: list[WordToken]) -> str:
    return "".join(t.stress_pattern for t in tokens if not t.unknown)


def check_line(tokens: list[WordToken], ctx: ValidationContext) -> RuleOutcome:
    if ctx.cadence_pattern is None:
        return RuleOutcome("warn", ["no cadence pattern set"])
    template = ctx.cadence_pattern.stress_template
    if not template or template == "?":
        return RuleOutcome("pass", [])
    actual = _line_stress(tokens)
    cmp_len = min(len(template), len(actual))
    mismatches = []
    for i in range(cmp_len):
        if template[i] == "?":
            continue
        if template[i] != actual[i]:
            mismatches.append(i)
    if not mismatches:
        return RuleOutcome("pass", [])
    if len(mismatches) <= 1:
        return RuleOutcome("warn", [f"cadence drift at position {mismatches[0]}"])
    # Demoted to warn — stress templates are a heuristic; Claude cannot fix ARPAbet
    # stress patterns, so a cadence FAIL in the correction loop just destroys meaning.
    return RuleOutcome("warn", [
        f"cadence drift: line stress {actual!r} vs template {template!r} differs at {mismatches}"
    ])
