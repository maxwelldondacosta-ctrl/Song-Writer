import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / ".claude" / "skills" / "songwriting"


# Pattern for a quoted line that looks like song lyrics
# (a quoted phrase in title-case-ish style, ≥4 words, with no punctuation indicating prose)
_LYRIC_QUOTE = re.compile(r'"[A-Z][a-z]+(?:\s+[A-Za-z][a-z]*){4,}"')


def test_constraints_doc_exists():
    p = SKILL_DIR / "reference" / "constraints.md"
    assert p.exists()
    body = p.read_text().lower()
    assert "copyrighted" in body
    assert "burn list" in body or "burn-list" in body
    assert "validation" in body
    assert "lock" in body


def test_no_obvious_copyrighted_lyric_quotes_in_skill():
    """Heuristic: scan every skill file for sustained song-lyric-style quoted strings."""
    flagged = []
    for p in SKILL_DIR.rglob("*.md"):
        body = p.read_text()
        for m in _LYRIC_QUOTE.finditer(body):
            phrase = m.group(0)
            # filter false positives: code-style quotes, descriptors with neutral content
            if any(t in phrase.lower() for t in ("call", "lookup", "endpoint", "section", "verse")):
                continue
            flagged.append((p.name, phrase))
    assert not flagged, f"possible copyrighted lyric quotes:\n  " + "\n  ".join(f"{n}: {p}" for n, p in flagged)


def test_no_artist_names_inside_descriptor_examples():
    """Descriptor examples in the skill must show that the artist's name is NOT in the descriptor itself."""
    body = (SKILL_DIR / "reference" / "descriptor-cache.md").read_text()
    # frank ocean is the seeded example; the descriptor in the example MUST NOT contain the name
    descriptor_block = re.search(r'"descriptor_short":\s*"([^"]+)"', body)
    if descriptor_block:
        assert "frank ocean" not in descriptor_block.group(1).lower()
