SONG_FULL = {
    "id": "cov-full",
    "title": "Full Coverage",
    "genre": "rnb",
    "sub_genre": "alt-rnb",
    "songwriter_lens": "frank-ocean",
    "intent": {
        "topic": "late call",
        "emotion_arc": "surrender",
        "story": {"event": "she calls", "emotion": "I should know better", "resolution": "I let her in"},
    },
    "production": {"bpm": 72, "structure_template": "rnb.intimate-confession", "energy_curve": [0.3, 0.7]},
    "sections": [
        {"id": "v1", "label": "Verse 1", "lock_state": "draft",
         "cadence_pattern": "melodic-glide", "lyrics": []},
    ],
}


def test_coverage_full_ready(client):
    client.post("/songs", json=SONG_FULL)
    body = client.get("/songs/cov-full/coverage").json()
    assert body["ready"] is True
    items = body["items"]
    assert items["production_fingerprint"] == "ok"
    assert items["emotion_tempo"] == "ok"
    assert items["songwriter_lens"] == "ok"
    assert items["cadence_patterns"] == "ok"
    # surrender × rnb has no exact bank — sibling-genre via kin map
    assert body["anchor_vocab"]["source"] in ("exact", "sibling-genre")
    assert body["anchor_vocab"]["count"] > 0
    assert body["anchor_vocab"]["would_use_llm"] is False


def test_coverage_flags_missing_emotion_tempo_for_custom_arc(client):
    payload = {**SONG_FULL, "id": "cov-custom-emotion",
               "intent": {**SONG_FULL["intent"], "emotion_arc": "wholly fabricated arc"}}
    client.post("/songs", json=payload)
    body = client.get("/songs/cov-custom-emotion/coverage").json()
    assert body["items"]["emotion_tempo"] == "missing"
    assert body["ready"] is False
    # No DB bank → would_use_llm true
    assert body["anchor_vocab"]["source"] == "none"
    assert body["anchor_vocab"]["would_use_llm"] is True


def test_coverage_flags_missing_lens(client):
    payload = {**SONG_FULL, "id": "cov-bad-lens", "songwriter_lens": "not-a-real-lens"}
    client.post("/songs", json=payload)
    body = client.get("/songs/cov-bad-lens/coverage").json()
    assert body["items"]["songwriter_lens"] == "missing"
    assert body["ready"] is False


def test_coverage_unset_lens_not_a_gap(client):
    payload = {**SONG_FULL, "id": "cov-no-lens", "songwriter_lens": None}
    client.post("/songs", json=payload)
    body = client.get("/songs/cov-no-lens/coverage").json()
    assert body["items"]["songwriter_lens"] == "unset"


def test_coverage_per_section_cadence_status(client):
    payload = {**SONG_FULL, "id": "cov-bad-cadence",
               "sections": [
                   {"id": "v1", "label": "Verse 1", "lock_state": "draft",
                    "cadence_pattern": "melodic-glide", "lyrics": []},
                   {"id": "v2", "label": "Verse 2", "lock_state": "draft",
                    "cadence_pattern": "made-up-cadence", "lyrics": []},
               ]}
    client.post("/songs", json=payload)
    body = client.get("/songs/cov-bad-cadence/coverage").json()
    per_section = body["cadence_per_section"]
    assert any(c["status"] == "ok" for c in per_section)
    assert any(c["status"] == "missing" for c in per_section)
    assert body["items"]["cadence_patterns"] == "missing"


def test_coverage_404(client):
    assert client.get("/songs/no-such-song/coverage").status_code == 404
