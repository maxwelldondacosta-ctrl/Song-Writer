"""Derive phonetic fields from CMUdict-style ARPAbet strings."""

from songwriter.seeds.phonemes import is_vowel
from songwriter.seeds.arpabet_ipa import strip_stress


def _tokens(arpabet: str) -> list[str]:
    return [t for t in arpabet.split() if t]


def syllable_count(arpabet: str) -> int:
    """Count syllables = count vowel phonemes (after stripping stress digits)."""
    return sum(1 for t in _tokens(arpabet) if is_vowel(strip_stress(t)))


def syllable_count_class(n: int) -> str:
    if n <= 1:
        return "mono"
    if n == 2:
        return "bi"
    return "multi"


def stress_pattern(arpabet: str) -> str:
    """Concatenate stress digits of vowels in order. Treat 2 as 1 (any stress)."""
    out = []
    for t in _tokens(arpabet):
        bare = strip_stress(t)
        if not is_vowel(bare):
            continue
        digit = t[-1] if t[-1].isdigit() else "0"
        out.append("1" if digit in {"1", "2"} else "0")
    return "".join(out)


from songwriter.seeds.phonemes import vowel_shape_label


def _last_stressed_vowel_index(tokens: list[str]) -> int | None:
    """Return index of the last vowel with primary or secondary stress.
    Falls back to the last vowel if no stressed vowel found."""
    last_any_vowel = None
    last_stressed = None
    for i, t in enumerate(tokens):
        bare = strip_stress(t)
        if not is_vowel(bare):
            continue
        last_any_vowel = i
        if t[-1] in {"1", "2"}:
            last_stressed = i
    return last_stressed if last_stressed is not None else last_any_vowel


def rhyme_class(arpabet: str) -> str:
    """Rhyme key: bare phonemes from the last stressed vowel to end, joined by '-'."""
    tokens = _tokens(arpabet)
    idx = _last_stressed_vowel_index(tokens)
    if idx is None:
        return ""
    bare = [strip_stress(t) for t in tokens[idx:]]
    return "-".join(bare)


def vowel_shape(arpabet: str) -> str:
    """Vowel-shape label of the last stressed vowel."""
    tokens = _tokens(arpabet)
    idx = _last_stressed_vowel_index(tokens)
    if idx is None:
        return ""
    return vowel_shape_label(strip_stress(tokens[idx]))


from songwriter.seeds.phonemes import attack_class, is_hard_consonant


def first_syllable_attack(arpabet: str) -> str:
    """Classify the first phoneme of the word as hard | soft | vowel."""
    tokens = _tokens(arpabet)
    if not tokens:
        return ""
    return attack_class(strip_stress(tokens[0]))


def consonant_density(arpabet: str) -> float:
    """Ratio of hard consonants to total phonemes."""
    tokens = _tokens(arpabet)
    if not tokens:
        return 0.0
    hard = sum(1 for t in tokens if is_hard_consonant(strip_stress(t)))
    return hard / len(tokens)
