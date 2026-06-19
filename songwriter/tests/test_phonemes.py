import pytest

from songwriter.seeds.phonemes import (
    is_vowel,
    is_consonant,
    attack_class,
    is_hard_consonant,
    vowel_shape_label,
)


@pytest.mark.parametrize("ph", ["AA", "AH", "AY", "ER", "OW"])
def test_is_vowel_true(ph):
    assert is_vowel(ph) is True


@pytest.mark.parametrize("ph", ["B", "CH", "DH", "S", "ZH"])
def test_is_vowel_false(ph):
    assert is_vowel(ph) is False
    assert is_consonant(ph) is True


@pytest.mark.parametrize("ph,expected", [
    ("P", "hard"), ("T", "hard"), ("K", "hard"),
    ("B", "hard"), ("D", "hard"), ("G", "hard"),
    ("CH", "hard"), ("JH", "hard"),
    ("F", "hard"), ("S", "hard"), ("SH", "hard"), ("TH", "hard"), ("HH", "hard"),
    ("M", "soft"), ("N", "soft"), ("NG", "soft"),
    ("L", "soft"), ("R", "soft"), ("W", "soft"), ("Y", "soft"),
    ("V", "soft"), ("Z", "soft"), ("ZH", "soft"), ("DH", "soft"),
    ("AA", "vowel"), ("IY", "vowel"), ("AY", "vowel"),
])
def test_attack_class(ph, expected):
    assert attack_class(ph) == expected


def test_is_hard_consonant_matches_attack():
    assert is_hard_consonant("P") is True
    assert is_hard_consonant("L") is False
    assert is_hard_consonant("AA") is False  # vowels are not "hard consonants"


@pytest.mark.parametrize("ph,expected", [
    ("AE", "short-A"), ("AA", "short-A-back"),
    ("EH", "short-E"), ("IH", "short-I"),
    ("AH", "short-U"), ("UH", "short-OO"),
    ("AO", "short-AW"),
    ("IY", "long-E"), ("UW", "long-U"),
    ("ER", "rhotic"),
    ("AY", "diphthong-AI"), ("AW", "diphthong-AU"),
    ("OY", "diphthong-OI"), ("EY", "diphthong-EI"),
    ("OW", "diphthong-OU"),
])
def test_vowel_shape_label(ph, expected):
    assert vowel_shape_label(ph) == expected
