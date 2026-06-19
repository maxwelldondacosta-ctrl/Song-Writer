from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.rhyme_cadence import check_section
from songwriter.api.validation.tokenizer import tokenize_line


def _ctx(rhyme_compat):
    return ValidationContext(
        cadence_pattern=CadencePattern(
            slug="x", syllable_template="?", stress_template="?", rhyme_compatibility=rhyme_compat
        ),
        emotion="x", sub_genre="x",
    )


def test_rhyme_pair_passes_when_perfect_allowed(conn):
    # "paid" and "stayed" both have rhyme_class "EY-D" → perfect rhyme pair
    lines = [tokenize_line("paid", conn),
             tokenize_line("stayed", conn)]
    assert check_section(lines, _ctx({"end": ["perfect", "near"]})).verdict == "pass"


def test_no_rhyme_warns(conn):
    # "love" (AH-V) and "smoke" (OW-K) don't share a rhyme class
    lines = [tokenize_line("love", conn), tokenize_line("smoke", conn)]
    assert check_section(lines, _ctx({"end": ["perfect"]})).verdict == "warn"
