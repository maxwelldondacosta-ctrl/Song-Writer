from pathlib import Path

import pytest

from songwriter.seeds import cmudict


FIXTURE = Path(__file__).parent / "fixtures" / "cmudict_sample.txt"


def test_parse_skips_comments_and_alternates():
    entries = cmudict.parse_file(FIXTURE)
    assert entries["love"] == "L AH1 V"
    assert entries["heart"] == "HH AA1 R T"
    assert entries["above"] == "AH0 B AH1 V"
    assert entries["start"] == "S T AA1 R T"
    # alternate pronunciation discarded
    assert entries["love"] != "L UH1 V"


def test_parse_lowercases_words():
    entries = cmudict.parse_file(FIXTURE)
    for k in entries:
        assert k == k.lower()


def test_download_caches(tmp_path, monkeypatch):
    target = tmp_path / "cmudict.dict"

    call_count = {"n": 0}
    def fake_get(url, timeout=None):
        call_count["n"] += 1
        class FakeResp:
            status_code = 200
            text = "LOVE  L AH1 V\n"
            def raise_for_status(self): pass
        return FakeResp()

    monkeypatch.setattr(cmudict.requests, "get", fake_get)
    cmudict.download(target)
    cmudict.download(target)  # should hit cache
    assert call_count["n"] == 1
    assert target.exists()
