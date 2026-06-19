from songwriter.api.validation import CadencePattern, ValidationContext
from songwriter.api.validation.phonetic_texture import check_line
from songwriter.api.validation.tokenizer import tokenize_line


def _ctx(emotion: str):
    return ValidationContext(
        cadence_pattern=None, emotion=emotion, sub_genre="x",
    )


def test_soft_emotion_pass_with_soft_words(conn):
    toks = tokenize_line("love linen pillow leaned", conn)  # mostly soft attacks, low density
    assert check_line(toks, _ctx("surrender")).verdict == "pass"


def test_soft_emotion_warn_with_hard_attacks(conn):
    toks = tokenize_line("typed kept paid stayed", conn)  # T/K/P/S — many hard attacks
    res = check_line(toks, _ctx("intimacy"))
    assert res.verdict == "warn"
