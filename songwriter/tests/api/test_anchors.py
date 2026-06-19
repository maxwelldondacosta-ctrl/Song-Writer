from unittest.mock import patch

from songwriter.api import vocab_resolver


SONG = {
    "id": "anchor-test",
    "title": "Anchor Test",
    "genre": "rnb",
    "sub_genre": "alt-rnb",
    "intent": {
        "topic": "late call",
        "emotion_arc": "surrender",
        "story": {"event": "she calls", "emotion": "I should know better", "resolution": "I let her in"},
    },
    "production": {"bpm": 72, "structure_template": "rnb.intimate-confession", "energy_curve": [0.3, 0.7, 0.85]},
    "sections": [],
}


def _post_song(client, body):
    r = client.post("/songs", json=body)
    assert r.status_code == 201, r.text


def setup_function(_):
    vocab_resolver.reset_cache()
    vocab_resolver.reset_hardness_cache()


def test_anchor_preview_db_path_no_llm(client):
    _post_song(client, SONG)
    r = client.get("/songs/anchor-test/anchor-preview")
    assert r.status_code == 200
    body = r.json()
    # `surrender` isn't an rnb bank, but kin map → rnb sibling-genre
    assert body["source"] == "sibling-genre"
    assert body["bank_slug"].startswith("rnb.")
    assert body["count"] > 0
    assert body["include_llm"] is False
    assert body["genre"] == "rnb"
    assert body["emotion"] == "surrender"


def test_anchor_preview_skips_llm_by_default(client):
    payload = {**SONG, "id": "no-bank", "intent": {**SONG["intent"], "emotion_arc": "wholly fabricated arc"}}
    _post_song(client, payload)
    # No bank matches; with include_llm=false should return source=none
    with patch("songwriter.api.vocab_resolver.ask_claude_json") as mock_llm:
        r = client.get("/songs/no-bank/anchor-preview")
    body = r.json()
    assert body["source"] == "none"
    assert body["count"] == 0
    mock_llm.assert_not_called()


def test_anchor_preview_llm_path_when_opted_in(client):
    payload = {**SONG, "id": "llm-yes", "intent": {**SONG["intent"], "emotion_arc": "wholly fabricated arc"}}
    _post_song(client, payload)
    fake = {"words": ["porch", "kettle", "doorway", "sleeve", "kept", "rehearsed", "elbow"]}
    with patch("songwriter.api.vocab_resolver.ask_claude_json", return_value=fake) as mock_llm:
        r = client.get("/songs/llm-yes/anchor-preview?include_llm=true")
    body = r.json()
    assert body["source"] == "llm-fallback"
    assert body["bank_slug"] is None
    assert body["count"] >= 5
    assert "porch" in body["words"]
    mock_llm.assert_called_once()


def test_anchor_preview_404_for_unknown_song(client):
    r = client.get("/songs/does-not-exist/anchor-preview")
    assert r.status_code == 404
