import pytest
from pydantic import ValidationError

from augurai.models import Model, Person
from augurai.store import Store


def test_roundtrip_sorted_and_stable(tmp_path):
    s = Store(tmp_path)
    p1 = Person(id="b", name="B", status="seed")
    p2 = Person(id="a", name="A", status="seed")
    assert s.write("people", [p1, p2]) is True
    assert [p.id for p in s.read("people", Person)] == ["a", "b"]
    assert s.write("people", [p2, p1]) is False
    assert (tmp_path / "people.json").read_text(encoding="utf-8").endswith("\n")


def test_missing_collection_is_empty(tmp_path):
    assert Store(tmp_path).read("models", Model) == []


def test_invalid_file_raises(tmp_path):
    (tmp_path / "people.json").write_text('[{"id": 1}]', encoding="utf-8")
    with pytest.raises(ValidationError):
        Store(tmp_path).read("people", Person)


def test_read_map_keys_by_id(tmp_path):
    s = Store(tmp_path)
    s.write("people", [Person(id="a", name="A", status="seed")])
    assert list(s.read_map("people", Person)) == ["a"]
