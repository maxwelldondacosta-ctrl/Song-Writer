from unittest.mock import patch


def _payload(slug="alt1"):
    return {
        "id": slug, "title": "Alt Test",
        "genre": "rnb", "sub_genre": "alt-rnb",
        "songwriter_lens": "frank-ocean",
        "intent": {
            "topic": "late call",
            "emotion_arc": "surrender",
            "story": {"event": "she calls late", "emotion": "I should know better", "resolution": "I let her in"},
        },
        "production": {"bpm": 72, "structure_template": "rnb.intimate-confession", "energy_curve": [0.4]},
        "sections": [{
            "id": "v1", "label": "Verse 1", "lock_state": "draft",
            "cadence_pattern": "melodic-glide",
            "lyrics": ["you called me late", "the kitchen counter cold", "i kept the porch light on"],
        }],
    }


def test_alternatives_returns_3_lines(client):
    client.post("/songs", json=_payload("a1"))
    fake = {"alternatives": ["one alt line", "another alt line", "third alt line"]}
    with patch("songwriter.api.routes.alternatives.ask_claude_json", return_value=fake):
        resp = client.post("/songs/a1/sections/v1/lines/1/alternatives?count=3")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["alternatives"]) == 3
    assert body["original"] == "the kitchen counter cold"
    assert body["section_id"] == "v1"
    assert body["line_index"] == 1


def test_alternatives_404_for_unknown_song(client):
    resp = client.post("/songs/nope/sections/v1/lines/0/alternatives")
    assert resp.status_code == 404


def test_alternatives_404_for_unknown_section(client):
    client.post("/songs", json=_payload("a3"))
    resp = client.post("/songs/a3/sections/nope/lines/0/alternatives")
    assert resp.status_code == 404


def test_alternatives_404_for_out_of_range_line(client):
    client.post("/songs", json=_payload("a4"))
    resp = client.post("/songs/a4/sections/v1/lines/99/alternatives")
    assert resp.status_code == 404


def test_alternatives_does_not_mutate_song(client):
    client.post("/songs", json=_payload("a5"))
    fake = {"alternatives": ["alt 1", "alt 2", "alt 3"]}
    before = client.get("/songs/a5").json()
    with patch("songwriter.api.routes.alternatives.ask_claude_json", return_value=fake):
        client.post("/songs/a5/sections/v1/lines/0/alternatives")
    after = client.get("/songs/a5").json()
    assert after["sections"][0]["lyrics"] == before["sections"][0]["lyrics"]


def test_alternatives_502_on_malformed_llm(client):
    client.post("/songs", json=_payload("a6"))
    with patch("songwriter.api.routes.alternatives.ask_claude_json", return_value={"foo": "bar"}):
        resp = client.post("/songs/a6/sections/v1/lines/0/alternatives")
    assert resp.status_code == 502


def test_alternatives_stream_emits_started_alt_done(client):
    """SSE variant should emit: started → alt(0) → alt(1) → alt(2) → done."""
    client.post("/songs", json=_payload("a7"))
    fake = {"alternatives": ["one alt", "two alt", "three alt"]}
    with patch("songwriter.api.routes.alternatives.ask_claude_json", return_value=fake):
        resp = client.get("/songs/a7/sections/v1/lines/0/alternatives/stream?count=3")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    # Verify event ordering and data shape
    events = [line for line in body.splitlines() if line.startswith("event:")]
    assert events[0] == "event: started"
    assert events[-1] == "event: done"
    assert events.count("event: alt") == 3
    # data: {"index": 0, "text": "one alt"} should be present
    assert '"text": "one alt"' in body
    assert '"text": "two alt"' in body
    assert '"text": "three alt"' in body


def test_alternatives_stream_emits_error_on_llm_failure(client):
    from songwriter.api.llm import LLMError
    client.post("/songs", json=_payload("a8"))
    with patch("songwriter.api.routes.alternatives.ask_claude_json", side_effect=LLMError("boom")):
        resp = client.get("/songs/a8/sections/v1/lines/0/alternatives/stream")
    assert resp.status_code == 200
    body = resp.text
    assert "event: error" in body
    assert "boom" in body
