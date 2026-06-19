"""Download + parse CMUdict.

Source: https://github.com/cmusphinx/cmudict (public domain)
"""

import re
from pathlib import Path

import requests

CMUDICT_URL = (
    "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict"
)

_ALT_SUFFIX = re.compile(r"\(\d+\)$")


def download(path: Path) -> None:
    """Download CMUdict to `path` if not already present."""
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(CMUDICT_URL, timeout=60)
    resp.raise_for_status()
    path.write_text(resp.text)


def parse_file(path: Path) -> dict[str, str]:
    """Parse CMUdict file → {lowercase_word: arpabet_string}.
    Drops comments, drops alternate-pronunciation entries (KEEP only primary)."""
    entries: dict[str, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(";;;"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        word, arpabet = parts
        word = word.lower()
        if _ALT_SUFFIX.search(word):
            continue
        if word in entries:
            continue
        entries[word] = arpabet.strip()
    return entries
