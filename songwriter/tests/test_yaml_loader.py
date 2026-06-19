import pytest

from songwriter.seeds.yaml_loader import load_yaml, load_all_in, require_keys


def test_load_yaml_returns_dict(tmp_path):
    p = tmp_path / "x.yml"
    p.write_text("name: foo\nvalue: 42\n")
    assert load_yaml(p) == {"name": "foo", "value": 42}


def test_load_all_in_finds_yml_and_yaml(tmp_path):
    (tmp_path / "a.yml").write_text("name: a\n")
    (tmp_path / "b.yaml").write_text("name: b\n")
    (tmp_path / "ignore.txt").write_text("name: c\n")
    items = load_all_in(tmp_path)
    names = sorted(d["name"] for d in items)
    assert names == ["a", "b"]


def test_load_all_in_recurses(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.yml").write_text("name: a\n")
    (tmp_path / "b.yml").write_text("name: b\n")
    items = load_all_in(tmp_path)
    assert len(items) == 2


def test_require_keys_passes_when_all_present():
    require_keys({"a": 1, "b": 2}, ["a", "b"], context="test")


def test_require_keys_raises_with_helpful_message():
    with pytest.raises(ValueError) as exc:
        require_keys({"a": 1}, ["a", "b"], context="myfile.yml")
    assert "myfile.yml" in str(exc.value)
    assert "b" in str(exc.value)
