def _payload(slug="suno1"):
    return {
        "id": slug, "title": "Suno Test",
        "genre": "rnb", "sub_genre": "alt-rnb",
        "songwriter_lens": "frank-ocean",
        "intent": {
            "topic": "late call",
            "emotion_arc": "surrender",
            "story": {"event": "she calls late", "emotion": "I should know better", "resolution": "I let her in"},
        },
        "production": {"bpm": 72, "structure_template": "rnb.intimate-confession", "energy_curve": [0.3, 0.5, 0.7, 0.85]},
        "sections": [
            {"id": "v1", "label": "Verse 1", "lock_state": "draft", "cadence_pattern": "melodic-glide", "lyrics": []},
            {"id": "ch", "label": "Chorus", "lock_state": "draft", "cadence_pattern": "pop-hook", "lyrics": []},
        ],
    }


def test_suno_prompt_includes_genre_bpm_lens(client):
    client.post("/songs", json=_payload("s1"))
    resp = client.post("/songs/s1/suno-prompt")
    assert resp.status_code == 200
    text = resp.json()["song"]["suno_prompt"]["current"].lower()
    assert "rnb" in text or "alt-rnb" in text
    assert "bpm" in text
    assert "frank ocean" in text  # lens display name


def test_suno_prompt_scrubs_burn_words(client):
    """Make a song whose lens / production cues might naturally include a burn-list
    word (none of our seed data does, but we still want to assert scrubbing works
    on the output path). Easiest way: use a sub-genre whose positives don't include
    burn words, then assert the final string contains no severity≥strong burn words."""
    client.post("/songs", json=_payload("s2"))
    resp = client.post("/songs/s2/suno-prompt")
    text = resp.json()["song"]["suno_prompt"]["current"].lower()
    for forbidden in ("neon", "ghost", "chrome", "midnight", "shadow"):
        assert forbidden not in text, f"burn word leaked into prompt: {forbidden}"


def test_suno_prompt_appends_history_on_regen(client):
    client.post("/songs", json=_payload("s3"))
    first = client.post("/songs/s3/suno-prompt").json()
    assert first["song"]["suno_prompt"]["current"]
    assert first["song"]["suno_prompt"]["history"] == []
    second = client.post("/songs/s3/suno-prompt").json()
    # history should have 1 entry now (the previous prompt)
    assert len(second["song"]["suno_prompt"]["history"]) == 1


def test_suno_prompt_404_for_unknown_song(client):
    resp = client.post("/songs/nonexistent/suno-prompt")
    assert resp.status_code == 404


def test_suno_prompt_handles_song_without_lens(client):
    payload = _payload("s5")
    payload["songwriter_lens"] = None
    client.post("/songs", json=payload)
    resp = client.post("/songs/s5/suno-prompt")
    assert resp.status_code == 200
    # No lens → no display name embedded
    text = resp.json()["song"]["suno_prompt"]["current"]
    assert text  # still a non-empty prompt


def test_suno_prompt_emits_structure_tags(client):
    """Suno mishandles sections without explicit [Verse]/[Chorus] tags
    (per r/SunoAI + hookgenius failure analyses, last30days 2026-04-30)."""
    payload = _payload("s7")
    payload["sections"] = [
        {"id": "v1", "label": "Verse 1", "lock_state": "draft", "cadence_pattern": "melodic-glide", "lyrics": []},
        {"id": "ch", "label": "Chorus", "lock_state": "draft", "cadence_pattern": "pop-hook", "lyrics": []},
        {"id": "v2", "label": "Verse 2", "lock_state": "draft", "cadence_pattern": "melodic-glide", "lyrics": []},
        {"id": "br", "label": "Bridge", "lock_state": "draft", "cadence_pattern": "storytelling", "lyrics": []},
    ]
    client.post("/songs", json=payload)
    body = client.post("/songs/s7/suno-prompt").json()
    text = body["song"]["suno_prompt"]["current"]
    for tag in ("[Verse 1]", "[Chorus]", "[Verse 2]", "[Bridge]"):
        assert tag in text, f"missing structure tag: {tag}"


def test_suno_prompt_warns_on_missing_lookups(client):
    """When the song's emotion has no emotion_tempo entry AND the LLM fallback
    fails, the response should expose explicit warnings. Bad lens slug always
    warns since there's no LLM fallback for lens."""
    from unittest.mock import patch
    from songwriter.api.llm import LLMError

    payload = _payload("s8")
    payload["intent"]["emotion_arc"] = "wholly fabricated arc"
    payload["songwriter_lens"] = "made-up-lens-slug"
    client.post("/songs", json=payload)

    # Force the emotion-tempo LLM fallback to fail so we still see the warning.
    with patch("songwriter.api.vocab_resolver.ask_claude_json",
               side_effect=LLMError("boom")):
        body = client.post("/songs/s8/suno-prompt").json()
    warnings = body.get("warnings", [])
    assert any("emotion_tempo" in w for w in warnings), warnings
    assert any("lens" in w for w in warnings), warnings


def test_suno_prompt_emotion_tempo_llm_fallback_recovers(client):
    """If the emotion_tempo DB entry is missing but Claude returns a valid
    range, the warning should NOT fire and the BPM line should appear."""
    from unittest.mock import patch
    from songwriter.api import vocab_resolver
    vocab_resolver.reset_emotion_tempo_cache()

    payload = _payload("s10")
    payload["intent"]["emotion_arc"] = "wholly fabricated arc"
    client.post("/songs", json=payload)
    fake = {"bpm_min": 70, "bpm_max": 84, "anti_prompts": ["overproduced", "edm-style stutter"]}
    with patch("songwriter.api.vocab_resolver.ask_claude_json", return_value=fake):
        body = client.post("/songs/s10/suno-prompt").json()
    assert body["sources"]["emotion_tempo"] == "llm-fallback"
    # No emotion_tempo warning since the fallback recovered
    assert not any("emotion_tempo" in w for w in body.get("warnings", []))
    assert "70" in body["song"]["suno_prompt"]["current"] or "84" in body["song"]["suno_prompt"]["current"]


def test_suno_prompt_no_warnings_when_all_lookups_hit(client):
    client.post("/songs", json=_payload("s9"))
    body = client.post("/songs/s9/suno-prompt").json()
    # The seeded surrender × alt-rnb pair + frank-ocean lens should all resolve
    assert body.get("warnings") == []


def test_suno_prompt_does_not_call_llm(client):
    """The endpoint should be deterministic templating, no claude --print invocation."""
    from unittest.mock import patch
    client.post("/songs", json=_payload("s6"))
    with patch("songwriter.api.llm.subprocess.run") as m:
        resp = client.post("/songs/s6/suno-prompt")
    assert resp.status_code == 200
    m.assert_not_called()
