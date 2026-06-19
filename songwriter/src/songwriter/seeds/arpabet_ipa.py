"""ARPAbet → IPA. Stress-aware for AH and ER (schwa vs wedge).

CMUdict ARPAbet uses 0/1/2 stress digits on vowels (0=unstressed, 1=primary, 2=secondary).
We use those digits to choose between schwa-family vs full-vowel IPA where it matters.
"""

# Stress-conditional vowel mapping: (stressed_form, unstressed_form)
_STRESS_CONDITIONAL = {
    "AH": ("ʌ", "ə"),
    "ER": ("ɝ", "ɚ"),
}

# Stress-invariant phoneme mapping
_BASE = {
    # Vowels
    "AA": "ɑ",
    "AE": "æ",
    "AO": "ɔ",
    "AW": "aʊ",
    "AY": "aɪ",
    "EH": "ɛ",
    "EY": "eɪ",
    "IH": "ɪ",
    "IY": "i",
    "OW": "oʊ",
    "OY": "ɔɪ",
    "UH": "ʊ",
    "UW": "u",
    # Consonants
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ",
    "K": "k", "L": "l", "M": "m", "N": "n",
    "NG": "ŋ", "P": "p", "R": "r", "S": "s",
    "SH": "ʃ", "T": "t", "TH": "θ", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}


def strip_stress(token: str) -> str:
    """Remove a trailing stress digit (0/1/2) from a phoneme token."""
    if token and token[-1].isdigit():
        return token[:-1]
    return token


def _phoneme_to_ipa(token: str) -> str:
    bare = strip_stress(token)
    if bare in _STRESS_CONDITIONAL:
        stressed, unstressed = _STRESS_CONDITIONAL[bare]
        # token had trailing digit if and only if vowel
        if token != bare and token[-1] == "0":
            return unstressed
        return stressed
    return _BASE.get(bare, "")


def arpabet_to_ipa(arpabet: str) -> str:
    """Convert a space-separated ARPAbet string to an IPA string."""
    return "".join(_phoneme_to_ipa(t) for t in arpabet.split())
