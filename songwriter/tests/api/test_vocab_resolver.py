"""Resolver covers: exact bank → sibling-genre → sibling-emotion → LLM fallback."""
from unittest.mock import patch

import pytest

from songwriter.api import vocab_resolver
from songwriter.api.vocab_resolver import (
    classify_emotion_hardness,
    resolve_vocab,
    reset_cache,
    reset_hardness_cache,
)
from songwriter.seeds import db as db_module


@pytest.fixture
def conn(built_db):
    c = db_module.connect(built_db)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _reset_caches():
    reset_cache()
    reset_hardness_cache()
    yield


def test_exact_bank_match(conn):
    words, source, slug = resolve_vocab(conn, genre="pop", emotion="confession")
    assert source == "exact"
    assert slug == "pop.confession"
    assert len(words) > 0
    assert "voicemail" in words


def test_sibling_genre_kin_match(conn):
    # `surrender` isn't a bank emotion — kin map should route it to rnb's
    # intimacy/longing/late-night/devotion within the same genre.
    words, source, slug = resolve_vocab(conn, genre="rnb", emotion="surrender")
    assert source == "sibling-genre"
    assert slug.startswith("rnb.")
    assert len(words) > 0


def test_sibling_genre_substring_match(conn):
    # custom emotion `late` should hit rnb.late-night
    words, source, slug = resolve_vocab(conn, genre="rnb", emotion="late")
    assert source == "sibling-genre"
    assert slug == "rnb.late-night"


def test_sibling_emotion_cross_genre_match(conn):
    # `breakup` isn't seeded for `metal`, but pop.breakup exists → cross-genre fallback
    words, source, slug = resolve_vocab(conn, genre="metal", emotion="breakup")
    assert source == "sibling-emotion"
    assert slug == "pop.breakup"
    assert len(words) > 0


def test_corpus_canonical_fallback(conn):
    # Insert a corpus-canonical bank for a genre that has no emotion-specific bank.
    # Using 'metal' + totally novel emotion so exact/sibling-genre/sibling-emotion all miss.
    from songwriter.seeds import db as db_module
    from songwriter.api.vocab_resolver import reset_cache

    # Seed a corpus-canonical bank manually
    bank_row = conn.execute(
        "INSERT INTO vocab_banks (slug, name) VALUES ('metal.corpus-canonical', 'Metal Corpus') RETURNING id"
    ).fetchone()
    bank_id = bank_row["id"]
    # Pick any word that's definitely in the test DB
    word_row = conn.execute("SELECT id FROM words LIMIT 1").fetchone()
    assert word_row, "words table is empty in test DB"
    conn.execute(
        "INSERT INTO vocab_bank_words (bank_id, word_id, emotional_weight) VALUES (?, ?, 1.0)",
        (bank_id, word_row["id"]),
    )
    conn.commit()
    reset_cache()

    words, source, slug = resolve_vocab(conn, genre="metal", emotion="completely-novel-arc-xyz")
    assert source == "corpus"
    assert slug == "metal.corpus-canonical"


def test_llm_fallback_when_no_bank_matches(conn):
    fake = {"words": ["porch", "kettle", "doorway", "sleeve", "kept", "rehearsed",
                      "elbow", "hallway", "spelt", "kettle", "lit", "leaned",
                      "rust", "thread"]}
    with patch(
        "songwriter.api.vocab_resolver.ask_claude_json", return_value=fake
    ) as mock_llm:
        words, source, slug = resolve_vocab(
            conn, genre="rnb", emotion="quiet vindication", topic="late call",
        )
    assert source == "llm-fallback"
    assert slug is None
    assert len(words) >= 10
    assert "porch" in words
    mock_llm.assert_called_once()


def test_llm_fallback_is_cached(conn):
    fake = {"words": ["porch", "kettle", "doorway", "sleeve", "kept"]}
    with patch(
        "songwriter.api.vocab_resolver.ask_claude_json", return_value=fake
    ) as mock_llm:
        resolve_vocab(conn, genre="rnb", emotion="quiet vindication")
        resolve_vocab(conn, genre="rnb", emotion="quiet vindication")
    assert mock_llm.call_count == 1


def test_llm_fallback_returns_none_on_llm_error(conn):
    from songwriter.api.llm import LLMError
    with patch(
        "songwriter.api.vocab_resolver.ask_claude_json",
        side_effect=LLMError("boom"),
    ):
        words, source, slug = resolve_vocab(
            conn, genre="rnb", emotion="quiet vindication",
        )
    assert source == "none"
    assert words == []


def test_empty_inputs_return_none(conn):
    words, source, slug = resolve_vocab(conn, genre="", emotion="")
    assert source == "none"
    assert words == []


def test_classify_hardness_static_soft():
    assert classify_emotion_hardness("surrender") == "soft"
    assert classify_emotion_hardness("nostalgia") == "soft"


def test_classify_hardness_static_hard():
    assert classify_emotion_hardness("defiance") == "hard"
    assert classify_emotion_hardness("escalation") == "hard"


def test_classify_hardness_llm_fallback_for_custom():
    fake = {"hardness": "soft"}
    with patch(
        "songwriter.api.vocab_resolver.ask_claude_json", return_value=fake
    ) as mock_llm:
        assert classify_emotion_hardness("quiet vindication") == "soft"
        # Cached on second call
        assert classify_emotion_hardness("quiet vindication") == "soft"
    assert mock_llm.call_count == 1


def test_classify_hardness_neutral_on_llm_error():
    from songwriter.api.llm import LLMError
    with patch(
        "songwriter.api.vocab_resolver.ask_claude_json",
        side_effect=LLMError("boom"),
    ):
        assert classify_emotion_hardness("untyped feeling") == "neutral"


def test_resolve_emotion_tempo_exact(conn):
    from songwriter.api.vocab_resolver import resolve_emotion_tempo, reset_emotion_tempo_cache
    reset_emotion_tempo_cache()
    et, source = resolve_emotion_tempo(
        conn, genre="rnb", sub_genre="alt-rnb", emotion="surrender",
    )
    assert source == "exact"
    assert isinstance(et["bpm_min"], int)
    assert isinstance(et["bpm_max"], int)


def test_resolve_emotion_tempo_llm_fallback(conn):
    from songwriter.api.vocab_resolver import resolve_emotion_tempo, reset_emotion_tempo_cache
    reset_emotion_tempo_cache()
    fake = {"bpm_min": 70, "bpm_max": 84,
            "anti_prompts": ["overproduced", "edm-style stutter"]}
    with patch(
        "songwriter.api.vocab_resolver.ask_claude_json", return_value=fake,
    ) as mock_llm:
        et, source = resolve_emotion_tempo(
            conn, genre="rnb", sub_genre="alt-rnb", emotion="completely-novel-arc",
        )
    assert source == "llm-fallback"
    assert et["bpm_min"] == 70
    assert et["bpm_max"] == 84
    assert "overproduced" in et["anti_prompts"]
    mock_llm.assert_called_once()


def test_resolve_emotion_tempo_rejects_implausible_bpm(conn):
    """Reject ranges outside 40-220 even if Claude returns them."""
    from songwriter.api.vocab_resolver import resolve_emotion_tempo, reset_emotion_tempo_cache
    reset_emotion_tempo_cache()
    bad = {"bpm_min": 30, "bpm_max": 350, "anti_prompts": []}
    with patch("songwriter.api.vocab_resolver.ask_claude_json", return_value=bad):
        et, source = resolve_emotion_tempo(
            conn, genre="rnb", sub_genre="alt-rnb", emotion="weird-arc",
        )
    assert source == "none"
    assert et == {}


def test_resolve_emotion_tempo_caches_llm_result(conn):
    from songwriter.api.vocab_resolver import resolve_emotion_tempo, reset_emotion_tempo_cache
    reset_emotion_tempo_cache()
    fake = {"bpm_min": 70, "bpm_max": 84, "anti_prompts": []}
    with patch(
        "songwriter.api.vocab_resolver.ask_claude_json", return_value=fake,
    ) as mock_llm:
        resolve_emotion_tempo(conn, genre="rnb", sub_genre="alt-rnb", emotion="novel-arc-2")
        resolve_emotion_tempo(conn, genre="rnb", sub_genre="alt-rnb", emotion="novel-arc-2")
    assert mock_llm.call_count == 1


def test_lru_cache_evicts_oldest():
    from songwriter.api.vocab_resolver import _LRU

    lru = _LRU(cap=3)
    lru["a"] = 1
    lru["b"] = 2
    lru["c"] = 3
    assert "a" in lru
    lru["d"] = 4  # evicts "a"
    assert "a" not in lru
    assert "d" in lru
    # Access "b" → moves to end; next insert evicts "c" not "b"
    _ = lru["b"]
    lru["e"] = 5
    assert "c" not in lru
    assert "b" in lru
