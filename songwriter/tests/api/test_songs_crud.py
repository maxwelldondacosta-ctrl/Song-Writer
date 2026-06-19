def _new_song_payload(slug="alpha"):
    return {
        "id": slug, "title": "Alpha",
        "genre": "pop", "sub_genre": "alt-pop",
        "intent": {
            "topic": "first song", "emotion_arc": "surrender",
            "story": {"event": "e", "emotion": "m", "resolution": "r"},
        },
        "production": {"bpm": 88, "structure_template": "pop.standard", "energy_curve": [0.4]},
        "sections": [],
    }


def test_create_song_persists_to_disk(client, settings):
    resp = client.post("/songs", json=_new_song_payload("alpha"))
    assert resp.status_code == 201
    assert (settings.songs_dir / "alpha.json").exists()


def test_create_duplicate_slug_409(client):
    client.post("/songs", json=_new_song_payload("dup"))
    resp = client.post("/songs", json=_new_song_payload("dup"))
    assert resp.status_code == 409


def test_get_song(client):
    client.post("/songs", json=_new_song_payload("getme"))
    resp = client.get("/songs/getme")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Alpha"


def test_get_missing_404(client):
    assert client.get("/songs/ghost").status_code == 404


def test_list_songs(client):
    client.post("/songs", json=_new_song_payload("one"))
    client.post("/songs", json=_new_song_payload("two"))
    resp = client.get("/songs")
    assert resp.status_code == 200
    slugs = {s["id"] for s in resp.json()}
    assert {"one", "two"} <= slugs


def test_put_song_updates(client):
    client.post("/songs", json=_new_song_payload("putme"))
    payload = _new_song_payload("putme")
    payload["title"] = "Renamed"
    resp = client.put("/songs/putme", json=payload)
    assert resp.status_code == 200
    assert client.get("/songs/putme").json()["title"] == "Renamed"


def test_put_slug_mismatch_400(client):
    client.post("/songs", json=_new_song_payload("p1"))
    payload = _new_song_payload("p1")
    payload["id"] = "different"
    resp = client.put("/songs/p1", json=payload)
    assert resp.status_code == 400
