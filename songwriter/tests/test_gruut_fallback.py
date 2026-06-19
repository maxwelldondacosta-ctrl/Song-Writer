import pytest

from songwriter.seeds.gruut_fallback import ipa_for_word


def test_ipa_for_known_word():
    # "shadow" — straightforward English, gruut should produce IPA
    ipa = ipa_for_word("shadow", "en")
    assert ipa, "expected non-empty IPA"
    # ʃ is the SH onset; presence is a basic sanity check
    assert "ʃ" in ipa


def test_ipa_for_word_handles_empty():
    assert ipa_for_word("", "en") == ""


def test_ipa_for_unknown_returns_empty_or_best_guess():
    out = ipa_for_word("zxqvb", "en")
    assert isinstance(out, str)
