"""Phoneme classification on bare ARPAbet (stress-stripped)."""

VOWELS = {
    "AA", "AE", "AH", "AO", "AW", "AY",
    "EH", "ER", "EY",
    "IH", "IY",
    "OW", "OY",
    "UH", "UW",
}

# Stops, affricates, and voiceless fricatives = "hard"
HARD_CONSONANTS = {
    "P", "T", "K", "B", "D", "G",
    "CH", "JH",
    "F", "S", "SH", "TH", "HH",
}

# Sonorants and voiced fricatives = "soft"
SOFT_CONSONANTS = {
    "M", "N", "NG", "L", "R", "W", "Y",
    "V", "Z", "ZH", "DH",
}

VOWEL_SHAPE = {
    "AE": "short-A",
    "AA": "short-A-back",
    "EH": "short-E",
    "IH": "short-I",
    "AH": "short-U",
    "UH": "short-OO",
    "AO": "short-AW",
    "IY": "long-E",
    "UW": "long-U",
    "ER": "rhotic",
    "AY": "diphthong-AI",
    "AW": "diphthong-AU",
    "OY": "diphthong-OI",
    "EY": "diphthong-EI",
    "OW": "diphthong-OU",
}


def is_vowel(phoneme: str) -> bool:
    return phoneme in VOWELS


def is_consonant(phoneme: str) -> bool:
    return phoneme in HARD_CONSONANTS or phoneme in SOFT_CONSONANTS


def is_hard_consonant(phoneme: str) -> bool:
    return phoneme in HARD_CONSONANTS


def attack_class(phoneme: str) -> str:
    if is_vowel(phoneme):
        return "vowel"
    if phoneme in HARD_CONSONANTS:
        return "hard"
    if phoneme in SOFT_CONSONANTS:
        return "soft"
    raise ValueError(f"unknown phoneme: {phoneme!r}")


def vowel_shape_label(phoneme: str) -> str:
    if phoneme not in VOWEL_SHAPE:
        raise ValueError(f"not a vowel or unsupported: {phoneme!r}")
    return VOWEL_SHAPE[phoneme]
