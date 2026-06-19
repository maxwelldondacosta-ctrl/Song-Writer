"""IPA via gruut for words missing from CMUdict.

We strip gruut's stress marks (ˈ, ˌ) and word/sentence boundaries from the
output to produce a flat IPA string compatible with our `words.ipa` column.
"""

from __future__ import annotations

try:
    from gruut import sentences as _gruut_sentences
except Exception:  # pragma: no cover
    _gruut_sentences = None


_STRIP = {"ˈ", "ˌ", " ", "‖", "|"}


def ipa_for_word(word: str, language: str = "en") -> str:
    if not word or _gruut_sentences is None:
        return ""
    chunks: list[str] = []
    try:
        for sentence in _gruut_sentences(word, lang=language):
            for w in sentence:
                if w.phonemes:
                    chunks.extend(w.phonemes)
    except Exception:
        return ""
    return "".join(c for c in "".join(chunks) if c not in _STRIP)
