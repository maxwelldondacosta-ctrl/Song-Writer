import re

from songwriter.api.validation import RuleOutcome, ValidationContext
from songwriter.api.validation.tokenizer import WordToken


# Words Suno reliably mispronounces because of silent letters or non-phonemic spelling.
# Source: hookgenius.app / r/SunoAI failure breakdowns 2026-04 (last30days research).
# Heuristic: when these appear in lyrics, Suno will mumble or say them wrong.
SILENT_LETTER_LANDMINES: frozenset[str] = frozenset({
    "psychology", "psychiatrist", "psychic",
    "knowledge", "knee", "knife", "knight", "knit", "know", "knot", "knob", "knock",
    "debt", "doubt", "subtle",
    "listen", "fasten", "soften", "often",
    "calm", "palm", "psalm", "almond", "salmon", "balm",
    "lamb", "climb", "comb", "bomb", "crumb", "limb", "thumb", "tomb", "womb",
    "half", "calf",
    "thigh", "high", "sigh", "weigh",
    "wrong", "wrap", "write", "wrist", "wrench", "wreck",
    "gnome", "gnaw",
    "hour", "honor", "honest", "heir",
    "rhyme", "rhythm",
    "island", "aisle",
    "scene", "science", "scissors",
    "could", "would", "should",
    "muscle",
    "answer", "sword",
})

# Common abbreviations Suno spells out letter-by-letter (ASAP → "A. S. A. P.").
# Detection requires raw casing; we accept the raw line text as an optional argument.
_ABBREV_PATTERN = re.compile(r"\b([A-Z]{2,5})\b")


def _syllables_in_line(tokens: list[WordToken]) -> int:
    return sum(t.syllables for t in tokens if not t.unknown)


def _parse_template(s: str) -> tuple[int | None, int | None]:
    s = s.strip()
    if s == "?" or not s:
        return None, None
    m = re.match(r"^(\d+)-(\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    if s.isdigit():
        n = int(s)
        return n - 2, n + 2  # ±2 tolerance
    return None, None


def _scan_landmines(tokens: list[WordToken], raw_line: str | None) -> list[str]:
    """Return user-facing warning strings for any Suno-landmine words on this line."""
    warnings: list[str] = []
    silent = sorted({t.word for t in tokens if t.word in SILENT_LETTER_LANDMINES})
    if silent:
        warnings.append(
            f"silent-letter word(s) Suno often mispronounces: {', '.join(silent)}"
        )
    if raw_line:
        # Detect ALL-CAPS abbreviations Suno spells out letter-by-letter
        abbrevs = sorted({m.group(1) for m in _ABBREV_PATTERN.finditer(raw_line) if m.group(1).upper() == m.group(1)})
        # Filter out single-word all-caps shouts (which are fine) — only flag if >=2 chars
        abbrevs = [a for a in abbrevs if 2 <= len(a) <= 5]
        if abbrevs:
            warnings.append(
                f"abbreviation(s) Suno will spell letter-by-letter: {', '.join(abbrevs)}"
            )
    return warnings


def check_line(
    tokens: list[WordToken],
    ctx: ValidationContext,
    *,
    raw_line: str | None = None,
) -> RuleOutcome:
    if ctx.cadence_pattern is None:
        return RuleOutcome("warn", ["no cadence pattern set; cannot check singability"])

    landmines = _scan_landmines(tokens, raw_line)

    lo, hi = _parse_template(ctx.cadence_pattern.syllable_template)
    if lo is None:
        # Wildcard cadence — only landmine warnings matter
        return RuleOutcome("warn" if landmines else "pass", landmines)

    n = _syllables_in_line(tokens)
    base_warn = list(landmines)
    if n < lo:
        return RuleOutcome("fail", [f"line has {n} syllables; cadence expects {lo}-{hi}", *base_warn])
    if n > hi:
        return RuleOutcome("warn", [f"line has {n} syllables; cadence expects {lo}-{hi}", *base_warn])
    return RuleOutcome("warn" if base_warn else "pass", base_warn)
