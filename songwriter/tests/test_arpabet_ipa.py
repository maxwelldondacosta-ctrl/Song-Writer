import pytest

from songwriter.seeds.arpabet_ipa import arpabet_to_ipa, strip_stress


@pytest.mark.parametrize("arpabet,ipa", [
    ("L AH1 V",       "lʌv"),         # love
    ("HH AA1 R T",    "hɑrt"),        # heart
    ("AH0 B AH1 V",   "əbʌv"),        # above
    ("S T AO1 R M",   "stɔrm"),       # storm
    ("M AY1 N D",     "maɪnd"),       # mind
    ("B IY1",         "bi"),          # bee
    ("CH OY1 S",      "tʃɔɪs"),       # choice
    ("ER1",           "ɝ"),           # stressed schwa-r
    ("B AH0 T ER0",   "bətɚ"),        # butter (unstressed ER → ɚ)
])
def test_arpabet_to_ipa_known_words(arpabet, ipa):
    assert arpabet_to_ipa(arpabet) == ipa


def test_strip_stress_removes_digits():
    assert strip_stress("AH1") == "AH"
    assert strip_stress("AH0") == "AH"
    assert strip_stress("ER2") == "ER"
    assert strip_stress("B") == "B"
