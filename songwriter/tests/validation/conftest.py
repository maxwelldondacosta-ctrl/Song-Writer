from pathlib import Path
import pytest

from songwriter.seeds import db as db_module
from songwriter.seeds.build import run as build_run


@pytest.fixture(scope="session")
def built_db(tmp_path_factory):
    target = tmp_path_factory.mktemp("data") / "songwriter.db"
    cache_dir = tmp_path_factory.mktemp("cache")
    fixture = Path(__file__).parent.parent / "fixtures" / "cmudict_vocab_words.txt"
    (cache_dir / "cmudict.dict").write_text(fixture.read_text())
    build_run(db_path=target, cache_dir=cache_dir)
    return target


@pytest.fixture
def conn(built_db):
    c = db_module.connect(built_db)
    yield c
    c.close()
