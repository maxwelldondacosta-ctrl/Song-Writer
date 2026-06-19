from unittest.mock import patch


def _payload(slug="draftme", sections=None):
    return {
        "id": slug, "title": "Draftable",
        "genre": "pop", "sub_genre": "alt-pop",
        "intent": {
            "topic": "late call from an ex",
            "emotion_arc": "surrender",
            "story": {
                "event": "she calls late",
                "emotion": "I should know better",
                "resolution": "I let her in anyway",
            },
        },
        "production": {"bpm": 88, "structure_template": "pop.standard", "energy_curve": [0.4]},
        "sections": sections if sections is not None else [
            {
                "id": "v1", "label": "Verse 1", "lock_state": "draft",
                "cadence_pattern": "melodic-glide", "lyrics": [],
            },
        ],
    }


def _good_lyrics_response(section_id="v1"):
    """A response that should pass most validations on a 1-section song."""
    return {
        "sections": [{
            "id": section_id,
            "lyrics": [
                "you called me late",
                "the kitchen counter cold",
                "i kept the porch light on",
                "i let you in anyway",
            ],
        }]
    }


def test_draft_writes_returned_lyrics_into_song(client):
    client.post("/songs", json=_payload("d1"))
    fake_pass_response = {"verdict": "pass", "per_line": []}
    with (
        patch("songwriter.api.routes.draft.ask_claude_json", return_value=_good_lyrics_response()),
        patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake_pass_response),
    ):
        resp = client.post("/songs/d1/draft")
    assert resp.status_code == 200
    body = resp.json()
    song = body["song"]
    v1 = next(s for s in song["sections"] if s["id"] == "v1")
    assert v1["lyrics"] == [
        "you called me late",
        "the kitchen counter cold",
        "i kept the porch light on",
        "i let you in anyway",
    ]
    assert "draft" in body
    assert body["draft"]["best_attempt"] >= 1
    assert body["draft"]["attempts_used"] >= 1


def test_draft_targets_specific_section(client):
    sections = [
        {"id": "v1", "label": "V1", "lock_state": "draft", "cadence_pattern": "melodic-glide", "lyrics": []},
        {"id": "v2", "label": "V2", "lock_state": "draft", "cadence_pattern": "melodic-glide", "lyrics": []},
    ]
    client.post("/songs", json=_payload("d2", sections))
    fake = {"sections": [{"id": "v2", "lyrics": ["only v2 line one", "only v2 line two"]}]}
    fake_validation = {"verdict": "pass", "per_line": []}
    with (
        patch("songwriter.api.routes.draft.ask_claude_json", return_value=fake),
        patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake_validation),
    ):
        resp = client.post("/songs/d2/draft?section=v2")
    body = resp.json()
    song = body["song"]
    v1 = next(s for s in song["sections"] if s["id"] == "v1")
    v2 = next(s for s in song["sections"] if s["id"] == "v2")
    assert v1["lyrics"] == []
    assert v2["lyrics"] == ["only v2 line one", "only v2 line two"]


def test_draft_409_when_no_empty_sections(client):
    sections = [{
        "id": "v1", "label": "V1", "lock_state": "draft",
        "cadence_pattern": "melodic-glide", "lyrics": ["already filled"],
    }]
    client.post("/songs", json=_payload("d3", sections))
    resp = client.post("/songs/d3/draft")
    assert resp.status_code == 409


def test_draft_404_for_unknown_section(client):
    client.post("/songs", json=_payload("d4"))
    resp = client.post("/songs/d4/draft?section=does-not-exist")
    assert resp.status_code == 404


def test_draft_404_for_unknown_song(client):
    resp = client.post("/songs/no-such-song/draft")
    assert resp.status_code == 404


def test_draft_502_when_first_attempt_returns_malformed(client):
    client.post("/songs", json=_payload("d6"))
    with patch("songwriter.api.routes.draft.ask_claude_json", return_value={"foo": "bar"}):
        resp = client.post("/songs/d6/draft")
    assert resp.status_code == 502


def test_draft_log_includes_per_attempt_score(client):
    """Whether or not the loop actually iterates is data-dependent (depends on which
    test-fixture words have phonetic data). The contract we DO assert: every attempt
    is logged with a score tuple, and the response shape includes attempts_used."""
    client.post("/songs", json=_payload("d7"))
    fake_story = {"verdict": "pass", "per_line": []}
    with (
        patch("songwriter.api.routes.draft.ask_claude_json", return_value=_good_lyrics_response()),
        patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake_story),
    ):
        resp = client.post("/songs/d7/draft?max_attempts=2")
    assert resp.status_code == 200
    body = resp.json()
    log = body["draft"]["log"]
    assert len(log) >= 1
    assert all("attempt" in entry for entry in log)
    assert any("score" in entry for entry in log)


def test_draft_scrubs_burn_list_words_from_lyrics(client):
    client.post("/songs", json=_payload("d8"))
    # Claude includes 'neon' and 'ghost' which are extreme-severity burn-list words
    fake = {"sections": [{
        "id": "v1",
        "lyrics": [
            "neon city walls",
            "ghost in the kitchen",
            "the porch was warm",
            "the lights stayed on",
        ],
    }]}
    fake_pass = {"verdict": "pass", "per_line": []}
    with (
        patch("songwriter.api.routes.draft.ask_claude_json", return_value=fake),
        patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake_pass),
    ):
        resp = client.post("/songs/d8/draft")
    assert resp.status_code == 200
    v1 = next(s for s in resp.json()["song"]["sections"] if s["id"] == "v1")
    full_text = " ".join(v1["lyrics"]).lower()
    assert "neon" not in full_text
    assert "ghost" not in full_text


def test_draft_response_includes_score(client):
    client.post("/songs", json=_payload("d9"))
    fake_pass = {"verdict": "pass", "per_line": []}
    with (
        patch("songwriter.api.routes.draft.ask_claude_json", return_value=_good_lyrics_response()),
        patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake_pass),
    ):
        body = client.post("/songs/d9/draft").json()
    assert "best_score" in body["draft"]
    s = body["draft"]["best_score"]
    assert s["passes"] >= 0 and s["warns"] >= 0 and s["fails"] >= 0
    assert isinstance(body["draft"]["all_pass"], bool)
