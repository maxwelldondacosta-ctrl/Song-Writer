from unittest.mock import patch


SONG = {
    "id": "integration", "title": "End-to-End",
    "genre": "rnb", "sub_genre": "alt-rnb",
    "intent": {"topic": "late call", "emotion_arc": "surrender",
               "story": {"event": "she calls late", "emotion": "I should know better",
                         "resolution": "I let her in anyway"}},
    "production": {"bpm": 72, "structure_template": "rnb.intimate-confession",
                   "energy_curve": [0.3, 0.7, 0.85]},
    "sections": [{
        "id": "v1", "label": "Verse 1", "lock_state": "draft",
        "cadence_pattern": "melodic-glide",
        "lyrics": ["you called me late", "said you couldn't sleep"],
    }],
}


def test_full_lifecycle(client, settings):
    # 1. create
    r = client.post("/songs", json=SONG)
    assert r.status_code == 201

    # 2. live snapshot via WS
    with client.websocket_connect("/ws/songs/integration") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"

        # 3. validate (deterministic only — keep test fast & offline)
        rv = client.post("/songs/integration/validate?include_llm=false")
        assert rv.status_code == 200

        # 4. WS receives an update
        update = ws.receive_json()
        assert update["type"] == "update"
        sec = update["song"]["sections"][0]
        for k in ("singability", "cadence", "phonetic_texture", "rhyme_cadence"):
            assert sec["validation"][k] in ("pass", "warn", "fail")

    # 5. on disk, validation results persisted
    fresh = client.get("/songs/integration").json()
    assert fresh["sections"][0]["validation"]["singability"] in ("pass", "warn", "fail")


def test_full_loop_with_llm_features_mocked(client, settings):
    """End-to-end: create → draft (mocked LLM) → validate-deterministic →
    cohesion check (mocked LLM) → suno-prompt (no LLM) → line alternatives
    (mocked LLM). Asserts every step persists to the saved JSON correctly."""
    payload = {
        **SONG, "id": "loop1",
        "sections": [
            {"id": "v1", "label": "Verse 1", "lock_state": "draft", "cadence_pattern": "melodic-glide", "lyrics": []},
            {"id": "ch", "label": "Chorus", "lock_state": "draft", "cadence_pattern": "pop-hook", "lyrics": []},
            {"id": "v2", "label": "Verse 2", "lock_state": "draft", "cadence_pattern": "melodic-glide", "lyrics": []},
        ],
    }
    assert client.post("/songs", json=payload).status_code == 201

    # 1. Draft — mock LLM for drafter, story-sentence, AND cohesion (draft now
    #    auto-runs cohesion on the winning candidate as part of the loop's
    #    final validate pass).
    fake_draft = {"sections": [
        {"id": "v1", "lyrics": ["you called me late", "the porch light still on", "I knew before you spoke", "I'd open the door"]},
        {"id": "ch",  "lyrics": ["I let you in anyway", "the porch light still on", "I knew it from the start", "I'd open the door"]},
        {"id": "v2", "lyrics": ["the kitchen counter cold", "the kettle on the burner gone", "we sat without a word", "I knew before you spoke"]},
    ]}
    fake_story = {"verdict": "pass", "per_line": []}
    fake_cohesion = {
        "verdict": "pass",
        "summary": "Porch-light image carries from verse to chorus to verse 2; pronoun stays consistent.",
        "issues": [],
    }
    with (
        patch("songwriter.api.routes.draft.ask_claude_json", return_value=fake_draft),
        patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake_story),
        patch("songwriter.api.validation.cohesion.ask_claude_json", return_value=fake_cohesion),
    ):
        rd = client.post("/songs/loop1/draft")
    assert rd.status_code == 200
    drafted = rd.json()["song"]
    assert all(s["lyrics"] for s in drafted["sections"])
    # Draft auto-runs cohesion on the winning candidate
    assert drafted["cohesion"]["verdict"] == "pass"
    assert "porch" in drafted["cohesion"]["summary"].lower()

    # 2. Deterministic validate — fast, no LLM. Should NOT wipe the cohesion
    #    result we just got from draft.
    rv = client.post("/songs/loop1/validate?include_llm=false")
    assert rv.status_code == 200
    body = rv.json()
    for s in body["sections"]:
        for rule in ("singability", "cadence", "phonetic_texture", "rhyme_cadence"):
            assert s["validation"][rule] in ("pass", "warn", "fail")
    # cohesion preserved from the draft step
    assert body["cohesion"]["verdict"] == "pass"

    # 3. Re-run cohesion via include_llm=true — re-checks and overwrites
    with (
        patch("songwriter.api.validation.cohesion.ask_claude_json", return_value=fake_cohesion),
        patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake_story),
    ):
        rc = client.post("/songs/loop1/validate?include_llm=true")
    assert rc.status_code == 200
    body = rc.json()
    assert body["cohesion"]["verdict"] == "pass"
    assert "porch" in body["cohesion"]["summary"].lower()

    # 4. Suno prompt build — deterministic, no LLM
    rs = client.post("/songs/loop1/suno-prompt")
    assert rs.status_code == 200
    suno = rs.json()["song"]["suno_prompt"]["current"]
    assert "[Verse 1]" in suno and "[Chorus]" in suno and "[Verse 2]" in suno
    assert "BPM" in suno or "bpm" in suno.lower()
    # burn-list scrub — no extreme/strong words leak through
    for forbidden in ("neon", "ghost", "ignite", "tonight", "delve"):
        assert forbidden not in suno.lower()

    # 5. Line alternatives — mocked LLM
    fake_alts = {"alternatives": ["the porch was warm", "the threshold caved", "I crossed the room"]}
    with patch("songwriter.api.routes.alternatives.ask_claude_json", return_value=fake_alts):
        ra = client.post("/songs/loop1/sections/v1/lines/0/alternatives?count=3")
    assert ra.status_code == 200
    alts = ra.json()["alternatives"]
    assert len(alts) == 3
    # alternatives endpoint does NOT mutate the song
    persisted = client.get("/songs/loop1").json()
    assert persisted["sections"][0]["lyrics"][0] == "you called me late"

    # 6. Final read — every result we computed is on disk
    final = client.get("/songs/loop1").json()
    assert final["cohesion"]["verdict"] == "pass"
    assert final["suno_prompt"]["current"] == suno
    assert final["sections"][0]["validation"]["singability"] in ("pass", "warn", "fail")


def test_validate_resets_cohesion_when_skipping_llm(client):
    """If a song was previously cohesion-checked, then re-validated with
    include_llm=false, the cohesion result should NOT be wiped — it should
    just stay stale until the next include_llm=true run."""
    payload = {
        **SONG, "id": "stale-cohesion",
        "sections": [
            {"id": "v1", "label": "Verse 1", "lock_state": "draft",
             "cadence_pattern": "melodic-glide",
             "lyrics": ["you called me late", "the porch light still on"]},
            {"id": "ch", "label": "Chorus", "lock_state": "draft",
             "cadence_pattern": "pop-hook",
             "lyrics": ["I let you in anyway", "the porch light still on"]},
        ],
    }
    client.post("/songs", json=payload)

    fake_cohesion = {"verdict": "warn", "summary": "needs work", "issues": []}
    fake_story = {"verdict": "pass", "per_line": []}
    with (
        patch("songwriter.api.validation.cohesion.ask_claude_json", return_value=fake_cohesion),
        patch("songwriter.api.validation.story_sentence.ask_claude_json", return_value=fake_story),
    ):
        client.post("/songs/stale-cohesion/validate?include_llm=true")

    after_llm = client.get("/songs/stale-cohesion").json()
    assert after_llm["cohesion"]["verdict"] == "warn"

    # Now run deterministic-only — cohesion should remain warn (we're not
    # invalidating it; user has to explicitly re-check)
    client.post("/songs/stale-cohesion/validate?include_llm=false")
    after_det = client.get("/songs/stale-cohesion").json()
    assert after_det["cohesion"]["verdict"] == "warn"


def test_descriptor_cache_round_trip(client):
    # seeded entries are pinned; first call to a seeded one increments use_count
    r1 = client.get("/descriptors/Frank%20Ocean")
    assert r1.status_code == 200
    assert r1.json()["source"] == "user-curated"

    # auto-LLM path on a fresh name
    fake = {
        "descriptor_short": "Smooth tenor with bright lead.",
        "descriptor_long": "Smooth tenor lead. Production is clean and bright with tight live drums and warm Rhodes pads. " * 3,
        "vocal_attributes": {"range": "tenor"}, "production_attrs": {"tempo_zone": "80-100"},
        "genre_context": "alt-rnb",
    }
    with patch("songwriter.api.routes.descriptors.ask_claude_json", return_value=fake):
        r2 = client.get("/descriptors/Some%20New%20Person")
    assert r2.status_code == 200
    assert r2.json()["source"] == "auto-llm"
    assert r2.json()["quality_state"] == "unverified"
