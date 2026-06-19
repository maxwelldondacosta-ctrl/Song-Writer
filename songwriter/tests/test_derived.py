import pytest

from songwriter.seeds.derived import (
    syllable_count,
    syllable_count_class,
    stress_pattern,
)


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V", 1),                # love
    ("HH AA1 R T", 1),             # heart
    ("AH0 B AH1 V", 2),            # above
    ("B AH0 T ER0", 2),            # butter
    ("UH0 N D ER0 S T AE1 N D", 3),# understand
])
def test_syllable_count(arpabet, expected):
    assert syllable_count(arpabet) == expected


@pytest.mark.parametrize("count,cls", [
    (1, "mono"),
    (2, "bi"),
    (3, "multi"),
    (4, "multi"),
])
def test_syllable_count_class(count, cls):
    assert syllable_count_class(count) == cls


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V", "1"),              # love (stressed monosyllable)
    ("AH0 B AH1 V", "01"),         # above (unstressed-stressed)
    ("B AH0 T ER0", "00"),         # butter (both unstressed; rare CMUdict edge)
    ("UH0 N D ER0 S T AE1 N D", "001"),  # understand
])
def test_stress_pattern(arpabet, expected):
    assert stress_pattern(arpabet) == expected


from songwriter.seeds.derived import rhyme_class, vowel_shape


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V",       "AH-V"),         # love
    ("AH0 B AH1 V",   "AH-V"),         # above (rhymes with love)
    ("HH AA1 R T",    "AA-R-T"),       # heart
    ("S T AA1 R T",   "AA-R-T"),       # start (rhymes with heart)
    ("M AY1 N D",     "AY-N-D"),       # mind
    ("B IY1",         "IY"),           # bee
    ("M IY1",         "IY"),           # me
    ("B AH0 T ER0",   "ER"),           # butter (no primary stress falls back to last vowel)
])
def test_rhyme_class(arpabet, expected):
    assert rhyme_class(arpabet) == expected


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V",       "short-U"),
    ("HH AA1 R T",    "short-A-back"),
    ("M AY1 N D",     "diphthong-AI"),
    ("B IY1",         "long-E"),
    ("S T AO1 R M",   "short-AW"),
])
def test_vowel_shape(arpabet, expected):
    assert vowel_shape(arpabet) == expected


from songwriter.seeds.derived import first_syllable_attack, consonant_density


@pytest.mark.parametrize("arpabet,expected", [
    ("L AH1 V",       "soft"),    # L (sonorant)
    ("HH AA1 R T",    "hard"),    # HH (voiceless fricative)
    ("AH0 B AH1 V",   "vowel"),   # starts with vowel
    ("S T AA1 R T",   "hard"),    # S
    ("M AY1 N D",     "soft"),    # M
])
def test_first_syllable_attack(arpabet, expected):
    assert first_syllable_attack(arpabet) == expected


def test_consonant_density_pure_hard():
    # "stark": S T AA1 R K → 5 phonemes, 3 hard (S, T, K), 1 soft (R), 1 vowel
    # density = hard / total = 3 / 5 = 0.6
    assert consonant_density("S T AA1 R K") == pytest.approx(0.6)


def test_consonant_density_pure_soft():
    # "moon": M UW1 N → 3 phonemes, 0 hard, 2 soft, 1 vowel
    assert consonant_density("M UW1 N") == pytest.approx(0.0)


def test_consonant_density_no_consonants():
    # "I": AY1 → 1 phoneme, 0 consonants
    assert consonant_density("AY1") == pytest.approx(0.0)
