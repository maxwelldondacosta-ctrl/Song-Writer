def test_list_genres(client):
    resp = client.get("/genres")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 12
    slugs = {g["slug"] for g in data}
    assert {"pop", "rnb"} <= slugs


def test_get_genre_with_sub_genres(client):
    resp = client.get("/genres/pop")
    assert resp.status_code == 200
    g = resp.json()
    assert g["slug"] == "pop"
    sub_slugs = {s["slug"] for s in g["sub_genres"]}
    assert {"dance-pop", "synth-pop"} <= sub_slugs


def test_get_unknown_genre_404(client):
    assert client.get("/genres/nonexistent").status_code == 404


def test_list_cadence_patterns(client):
    resp = client.get("/cadence-patterns")
    assert resp.status_code == 200
    assert len(resp.json()) == 10


def test_get_vocab_bank_words(client):
    resp = client.get("/vocab-banks/pop.confession/words")
    assert resp.status_code == 200
    words = {w["word"] for w in resp.json()}
    assert "voicemail" in words


def test_get_word_phonetics(client):
    resp = client.get("/words/love")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ipa"] == "lʌv"
    assert body["rhyme_class"] == "AH-V"


def test_get_word_404(client):
    assert client.get("/words/zxqvbnm").status_code == 404


def test_rhymes_for_word_returns_same_class(client):
    resp = client.get("/rhymes?word=love&limit=20")
    assert resp.status_code == 200
    out = resp.json()
    assert out["rhyme_class"] == "AH-V"
    rhymes = {w["word"] for w in out["words"]}
    assert "above" in rhymes
    assert "love" not in rhymes  # query word excluded


def test_burn_list(client):
    resp = client.get("/burn-list")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 50
    words = {b["word"] for b in data}
    assert "neon" in words
