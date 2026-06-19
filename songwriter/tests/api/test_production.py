def test_get_production_fingerprint(client):
    resp = client.get("/production-fingerprints/alt-rnb")
    assert resp.status_code == 200
    body = resp.json()
    negs = body["negative_descriptors"]
    assert any("bright" in n.lower() or "EDM" in n for n in negs)


def test_get_production_fingerprint_404(client):
    assert client.get("/production-fingerprints/nonexistent").status_code == 404


def test_get_emotion_tempo(client):
    resp = client.get("/emotion-tempo?emotion=surrender&sub_genre=alt-rnb")
    assert resp.status_code == 200
    body = resp.json()
    assert 60 <= body["bpm_min"] <= body["bpm_max"] <= 100
    assert "EDM-build" in body["anti_prompts"]


def test_get_emotion_tempo_404(client):
    assert client.get("/emotion-tempo?emotion=apathy&sub_genre=alt-rnb").status_code == 404


def test_list_structure_templates(client):
    resp = client.get("/structure-templates")
    assert resp.status_code == 200
    slugs = {t["slug"] for t in resp.json()}
    assert "pop.standard" in slugs
    assert "rnb.intimate-confession" in slugs
