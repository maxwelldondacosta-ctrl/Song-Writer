from unittest.mock import patch


def _payload(slug="vsong", section_lyrics=None):
    return {
        "id": slug, "title": "V",
        "genre": "rnb", "sub_genre": "alt-rnb",
        "intent": {
            "topic": "test", "emotion_arc": "surrender",
            "story": {"event": "e", "emotion": "m", "resolution": "r"},
        },
        "production": {"bpm": 72, "structure_template": "rnb.intimate-confession", "energy_curve": [0.4]},
        "sections": [{
            "id": "v1", "label": "Verse 1", "lock_state": "draft",
            "cadence_pattern": "melodic-glide",
            "lyrics": section_lyrics or ["you called me late", "said you couldn't sleep"],
        }],
    }


def test_validate_runs_deterministic_only_when_skip_llm(client):
    client.post("/songs", json=_payload("v1"))
    resp = client.post("/songs/v1/validate?include_llm=false")
    assert resp.status_code == 200
    sec = resp.json()["sections"][0]["validation"]
    # deterministic engines ran
    assert sec["singability"] in ("pass", "warn", "fail")
    assert sec["cadence"] in ("pass", "warn", "fail")
    assert sec["phonetic_texture"] in ("pass", "warn", "fail")
    assert sec["rhyme_cadence"] in ("pass", "warn", "fail")
    # LLM-judged skipped
    assert sec["story_sentence"] == "unrun"


def test_validate_runs_llm_when_requested(client):
    fake = {"verdict": "pass", "per_line": []}
    client.post("/songs", json=_payload("v2"))
    with patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake):
        resp = client.post("/songs/v2/validate?include_llm=true")
    assert resp.status_code == 200
    assert resp.json()["sections"][0]["validation"]["story_sentence"] == "pass"


def test_validate_writes_back_to_disk(client, settings):
    client.post("/songs", json=_payload("v3"))
    client.post("/songs/v3/validate?include_llm=false")
    fresh = client.get("/songs/v3").json()
    assert fresh["sections"][0]["validation"]["singability"] in ("pass", "warn", "fail")
