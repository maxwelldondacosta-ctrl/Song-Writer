"""Default section structures with genre-aware cadence pattern selection.

Using the right cadence for the genre prevents the singability validator from
flagging correct rap lines as failing because they were measured against a pop
syllable target.
"""

_GENRE_CADENCES: dict[str, dict[str, str]] = {
    "trap":    {"verse": "corpus-rap-verse",   "chorus": "corpus-rap-chorus",   "bridge": "storytelling"},
    "drill":   {"verse": "corpus-rap-verse",   "chorus": "corpus-rap-chorus",   "bridge": "corpus-rap-bridge"},
    "rap":     {"verse": "corpus-rap-verse",   "chorus": "corpus-rap-chorus",   "bridge": "corpus-rap-bridge"},
    "hip-hop": {"verse": "corpus-rap-verse",   "chorus": "corpus-rap-chorus",   "bridge": "corpus-rap-bridge"},
    "grime":   {"verse": "corpus-grime-verse", "chorus": "corpus-grime-chorus", "bridge": "corpus-grime-bridge"},
    "rnb":     {"verse": "corpus-rnb-verse",   "chorus": "corpus-soul-chorus",  "bridge": "melodic-glide"},
    "soul":    {"verse": "corpus-soul-verse",  "chorus": "corpus-soul-chorus",  "bridge": "melodic-glide"},
    "rock":    {"verse": "corpus-rock-verse",  "chorus": "corpus-rock-chorus",  "bridge": "corpus-rock-bridge"},
    "metal":   {"verse": "corpus-metal-verse", "chorus": "corpus-metal-chorus", "bridge": "melodic-glide"},
    "folk":    {"verse": "corpus-folk-chorus", "chorus": "corpus-folk-chorus",  "bridge": "melodic-glide"},
    "country": {"verse": "storytelling",       "chorus": "pop-hook",            "bridge": "melodic-glide"},
    "edm":     {"verse": "corpus-edm-verse",   "chorus": "corpus-edm-other",    "bridge": "corpus-edm-bridge"},
    "pop":     {"verse": "melodic-glide",      "chorus": "pop-hook",            "bridge": "melodic-glide"},
}

_DEFAULT_CADENCES: dict[str, str] = {
    "verse": "melodic-glide",
    "chorus": "pop-hook",
    "bridge": "melodic-glide",
}


def _resolve_cadences(slug: str) -> dict[str, str] | None:
    slug = (slug or "").lower().replace(" ", "-")
    if slug in _GENRE_CADENCES:
        return _GENRE_CADENCES[slug]
    for key, cadences in _GENRE_CADENCES.items():
        if key in slug or slug in key:
            return cadences
    return None


def sections_for_genre(genre_slug: str, sub_genre_slug: str) -> list[dict]:
    """4-section structure with cadence patterns matched to the song's genre."""
    cadences = _resolve_cadences(sub_genre_slug) or _resolve_cadences(genre_slug) or _DEFAULT_CADENCES
    v = cadences.get("verse", "melodic-glide")
    c = cadences.get("chorus", "pop-hook")
    return [
        {"id": "v1",  "label": "Verse 1", "cadence": v},
        {"id": "ch1", "label": "Chorus",  "cadence": c},
        {"id": "v2",  "label": "Verse 2", "cadence": v},
        {"id": "ch2", "label": "Chorus",  "cadence": c},
    ]


# Legacy constant — kept so any stale imports don't break
DEFAULT_SECTIONS = sections_for_genre("pop", "pop")
