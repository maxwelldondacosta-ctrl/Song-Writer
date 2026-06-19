from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.cadence import check_line
from songwriter.api.validation.tokenizer import tokenize_line


def _ctx(stress: str):
    return ValidationContext(
        cadence_pattern=CadencePattern(
            slug="x", syllable_template="?", stress_template=stress, rhyme_compatibility={}
        ),
        emotion="x", sub_genre="x",
    )


def test_cadence_wildcard_passes(conn):
    toks = tokenize_line("you called me late tonight", conn)
    assert check_line(toks, _ctx("?")).verdict == "pass"


def test_cadence_pass_when_stress_matches(conn):
    # "love" has stress pattern "1"; template "1" passes
    toks = tokenize_line("love", conn)
    assert check_line(toks, _ctx("1")).verdict == "pass"


def test_cadence_drift_warns(conn):
    # "love love" → "11"; template "10" → 1 mismatch → warn
    toks = tokenize_line("love love", conn)
    assert check_line(toks, _ctx("10")).verdict == "warn"
