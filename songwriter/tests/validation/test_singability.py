from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.singability import check_line
from songwriter.api.validation.tokenizer import tokenize_line


def _ctx(template: str):
    return ValidationContext(
        cadence_pattern=CadencePattern(
            slug="x", syllable_template=template, stress_template="?", rhyme_compatibility={}
        ),
        emotion="surrender", sub_genre="pop.alt-pop",
    )


def test_singability_pass_in_range(conn):
    # "tomorrow balcony" → 3 + 3 = 6 syllables; template "6-9" → pass
    toks = tokenize_line("tomorrow balcony", conn)
    res = check_line(toks, _ctx("6-9"))
    assert res.verdict == "pass"


def test_singability_fail_below_range(conn):
    # "love" → 1 syllable; template "6-9" → fail
    toks = tokenize_line("love", conn)
    res = check_line(toks, _ctx("6-9"))
    assert res.verdict == "fail"


def test_singability_warn_above_range(conn):
    # "anniversary elevator tomorrow balcony" → 5+4+3+3 = 15 syllables; template "6-9" → warn
    toks = tokenize_line("anniversary elevator tomorrow balcony", conn)
    res = check_line(toks, _ctx("6-9"))
    assert res.verdict == "warn"


def test_singability_wildcard_passes(conn):
    toks = tokenize_line("tomorrow balcony love", conn)
    res = check_line(toks, _ctx("?"))
    assert res.verdict == "pass"


def test_silent_letter_word_warns(conn):
    """Suno mispronounces silent-letter words (psychology, knowledge, debt).
    Last30days 2026-04: hookgenius / r/SunoAI flagged as top Suno failure."""
    toks = tokenize_line("the psychology of late nights", conn)
    res = check_line(toks, _ctx("?"), raw_line="the psychology of late nights")
    assert res.verdict == "warn"
    assert any("psychology" in w for w in res.warnings)


def test_abbreviation_warns(conn):
    """Suno spells ASAP letter-by-letter."""
    toks = tokenize_line("ASAP I'll find another way", conn)
    res = check_line(toks, _ctx("?"), raw_line="ASAP I'll find another way")
    assert res.verdict == "warn"
    assert any("ASAP" in w for w in res.warnings)


def test_clean_line_passes_with_raw(conn):
    toks = tokenize_line("you called me late tomorrow", conn)
    res = check_line(toks, _ctx("?"), raw_line="you called me late tomorrow")
    assert res.verdict == "pass"
    assert res.warnings == []
