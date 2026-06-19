def test_list_songwriter_profiles(client):
    resp = client.get("/songwriter-profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 10
    slugs = {p["slug"] for p in data}
    assert {"frank-ocean", "diane-warren"} <= slugs


def test_filter_by_genre(client):
    resp = client.get("/songwriter-profiles?genre=rnb")
    assert resp.status_code == 200
    slugs = {p["slug"] for p in resp.json()}
    assert "frank-ocean" in slugs
    assert "diane-warren" not in slugs


def test_filter_by_role(client):
    resp = client.get("/songwriter-profiles?role=pure-songwriter")
    assert resp.status_code == 200
    data = resp.json()
    assert all(p["role"] == "pure-songwriter" for p in data)
    slugs = {p["slug"] for p in data}
    assert "diane-warren" in slugs  # baseline pure-songwriter


def test_get_one_profile(client):
    resp = client.get("/songwriter-profiles/frank-ocean")
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "self-writing-artist"
    assert isinstance(body["craft_signature"], list)
    assert "adoption_prompt" in body and len(body["adoption_prompt"]) > 50


def test_unknown_profile_404(client):
    assert client.get("/songwriter-profiles/nope").status_code == 404
