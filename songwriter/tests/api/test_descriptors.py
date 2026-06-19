from unittest.mock import patch


def test_get_descriptor_hit_increments_use_count(client, settings):
    # frank-ocean is seeded; first call increments to 1
    r1 = client.get("/descriptors/frank-ocean")
    assert r1.status_code == 200
    body = r1.json()
    assert body["canonical_name"] == "Frank Ocean"
    assert body["use_count"] == 1
    r2 = client.get("/descriptors/frank-ocean")
    assert r2.json()["use_count"] == 2


def test_get_descriptor_normalizes_name(client):
    # "The Frank Ocean" should normalize to "frank ocean" → hit
    resp = client.get("/descriptors/the%20frank%20ocean")
    assert resp.status_code == 200
    assert resp.json()["canonical_name"] == "Frank Ocean"


def test_get_descriptor_miss_invokes_llm_and_caches(client):
    fake_payload = {
        "descriptor_short": "Bright tenor lead with reverb-soaked production.",
        "descriptor_long": "A bright tenor lead. Production is reverb-drenched with bouncy synth bass and bright pop snares; vocals double-tracked on chorus.",
        "vocal_attributes": {"range": "tenor", "character": "bright"},
        "production_attrs": {"tempo_zone": "100-120"},
        "genre_context": "alt-pop",
    }
    with patch("songwriter.api.routes.descriptors.ask_claude_json", return_value=fake_payload) as m:
        resp = client.get("/descriptors/some-new-artist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "auto-llm"
    assert body["quality_state"] == "unverified"
    assert body["use_count"] == 1
    # second request hits cache, no new LLM call
    with patch("songwriter.api.routes.descriptors.ask_claude_json") as m2:
        client.get("/descriptors/some-new-artist")
        m2.assert_not_called()


def test_descriptor_scrubs_burn_list_words(client):
    fake = {
        "descriptor_short": "A neon, ghost-like presence with chrome production.",
        "descriptor_long": "Long form. Neon glow in the chorus, ghost-like delays, chrome high-end. " * 3,
        "vocal_attributes": {},
        "production_attrs": {},
        "genre_context": "synth-pop",
    }
    with patch("songwriter.api.routes.descriptors.ask_claude_json", return_value=fake):
        resp = client.get("/descriptors/another-new-artist")
    body = resp.json()
    # burn-list words must be scrubbed from short and long
    for w in ("neon", "ghost", "chrome"):
        assert w.lower() not in body["descriptor_short"].lower()
        assert w.lower() not in body["descriptor_long"].lower()
