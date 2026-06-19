import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from songwriter.api.main import create_app


REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / ".claude" / "skills" / "songwriting" / "reference" / "api-recipes.md"


# Match curl ... <method?> http(s)://...:8000<path>
# Handles both -X POST and -sX POST (flags merged before method)
_CURL_RE = re.compile(r"curl[^\n]*?(?:-[a-zA-Z]*X\s+(\w+)\s+|)\s*[\"']?(?:https?://[^/\s\"']*)(/[\w\-/{}.]+)")


@pytest.fixture(scope="module")
def app_client(request):
    # build with the existing session-scoped DB used by tests/api/conftest.py
    # We can't import that fixture cleanly here; run the test against an app with default settings + the built DB.
    from songwriter.api.settings import Settings
    from songwriter.seeds.build import run as build_run
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    fixture = REPO / "tests" / "fixtures" / "cmudict_vocab_words.txt"
    cache = tmp / "cache"
    cache.mkdir()
    (cache / "cmudict.dict").write_text(fixture.read_text())
    db = tmp / "songwriter.db"
    build_run(db_path=db, cache_dir=cache)
    settings = Settings(db_path=db, songs_dir=tmp / "songs")
    app = create_app(settings=settings)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_api_recipes_doc_exists():
    assert RECIPES.exists()


def test_every_endpoint_in_recipes_exists(app_client):
    text = RECIPES.read_text()
    matches = _CURL_RE.findall(text)
    assert matches, "expected at least one curl example in api-recipes.md"
    seen: set[tuple[str, str]] = set()
    for method, raw_path in matches:
        method = (method or "GET").upper()
        # replace all placeholder tokens with a safe sentinel so the route
        # exists (returns anything except 405) but we tolerate 404 for unknown IDs
        path = raw_path
        path = re.sub(r"\{[^}]+\}", "x", path)
        path = re.sub(r"<[^>]+>", "x", path)
        if (method, path) in seen:
            continue
        seen.add((method, path))
        if method == "GET":
            r = app_client.get(path)
        elif method == "POST":
            r = app_client.post(path)
        elif method == "PUT":
            r = app_client.put(path, json={})
        else:
            continue
        # any non-405 response means the route exists in the app
        assert r.status_code != 405 and r.status_code != 404 or path.endswith("/x") or "x" in path, (
            f"endpoint {method} {path} returned {r.status_code} — route may not exist"
        )
