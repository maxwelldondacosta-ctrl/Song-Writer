from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from songwriter.api.main import create_app
from songwriter.api.settings import Settings
from songwriter.seeds import db as db_module
from songwriter.seeds.build import run as build_run


@pytest.fixture(scope="session")
def built_db(tmp_path_factory):
    """Build a real DB once per test session using the small CMUdict fixture."""
    target = tmp_path_factory.mktemp("data") / "songwriter.db"
    cache_dir = tmp_path_factory.mktemp("cache")
    fixture = Path(__file__).parent.parent / "fixtures" / "cmudict_vocab_words.txt"
    (cache_dir / "cmudict.dict").write_text(fixture.read_text())
    build_run(db_path=target, cache_dir=cache_dir)
    return target


@pytest.fixture
def settings(built_db, tmp_path) -> Settings:
    return Settings(db_path=built_db, songs_dir=tmp_path / "songs")


@pytest.fixture
def client(settings) -> TestClient:
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c
