from app.utils.uuidv7 import uuid7
from app.utils.tree import descendant_ids


def test_uuid7_format_and_ordering():
    a = uuid7()
    b = uuid7()
    assert len(a) == 36 and a.count("-") == 4
    assert a != b
    assert a < b  # UUIDv7 is time-ordered


def test_descendant_ids():
    rows = [("1", None), ("2", "1"), ("3", "1"), ("4", "2"), ("5", None)]
    assert descendant_ids(rows, "1") == {"1", "2", "3", "4"}
    assert descendant_ids(rows, "2") == {"2", "4"}
    assert descendant_ids(rows, "5") == {"5"}


def test_descendant_ids_missing_root():
    assert descendant_ids([("1", None)], "x") == {"x"}
