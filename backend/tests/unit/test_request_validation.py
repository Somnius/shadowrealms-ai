import pytest

from services.request_validation import body_object, optional_str, strict_bool, strict_int
from services.v5_dice import validate_reroll_indices


def test_body_object():
    assert body_object(None) == {}
    assert body_object({"a": 1}) == {"a": 1}
    for bad in ([], [1], "x", 3, True):
        with pytest.raises(ValueError):
            body_object(bad)


def test_strict_int():
    assert strict_int(None, "n", 6) == 6
    assert strict_int("", "n", 6) == 6
    assert strict_int(3, "n") == 3
    assert strict_int("4", "n") == 4
    assert strict_int(" -2 ", "n") == -2
    assert strict_int(5.0, "n") == 5
    for bad in (True, False, 2.5, "2.5", "abc", [1], {"a": 1}):
        with pytest.raises(ValueError):
            strict_int(bad, "n")
    assert strict_int(5, "h", None, 0, 5) == 5
    with pytest.raises(ValueError):
        strict_int(6, "h", None, 0, 5)
    with pytest.raises(ValueError):
        strict_int(-1, "h", None, 0, 5)


def test_strict_bool():
    assert strict_bool(None, "b") is False
    assert strict_bool(None, "b", True) is True
    assert strict_bool(True, "b") is True
    assert strict_bool(False, "b") is False
    for bad in ("false", "true", 0, 1, [], {}):
        with pytest.raises(ValueError):
            strict_bool(bad, "b")


def test_optional_str():
    assert optional_str(None, "s", "d") == "d"
    assert optional_str("  ", "s", "d") == "d"
    assert optional_str(" hi ", "s") == "hi"
    for bad in (1, True, ["x"], {"a": 1}):
        with pytest.raises(ValueError):
            optional_str(bad, "s")
    with pytest.raises(ValueError):
        optional_str("abcdef", "s", max_len=3)


def test_reroll_indices_must_be_ints():
    assert validate_reroll_indices([1, 2, 3], [0, 2]) == [0, 2]
    for bad in ([True], [False], [0.0], [0.9], ["0"], [None]):
        with pytest.raises(ValueError):
            validate_reroll_indices([1, 2, 3], bad)
