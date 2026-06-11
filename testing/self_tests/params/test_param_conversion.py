from __future__ import annotations

from tools.param_conversion import (
    normalize_value,
    to_bool,
    to_float,
    to_int,
    to_string,
    to_string_list,
    wire_string,
)


def test_to_int_accepts_float_shaped_values() -> None:
    assert to_int(3, default=0) == 3
    assert to_int(3.0, default=0) == 3
    assert to_int("3", default=0) == 3
    assert to_int("3.0", default=0) == 3


def test_to_int_returns_default_for_invalid_values() -> None:
    assert to_int("", default=7) == 7
    assert to_int("abc", default=7) == 7
    assert to_int("3.5", default=7) == 7


def test_basic_param_conversions() -> None:
    assert to_float("3.5", default=0.0) == 3.5
    assert to_bool("true", default=False) is True
    assert to_bool("0", default=True) is False
    assert to_string(3.0) == "3"
    assert to_string(3.5) == "3.5"
    assert to_string_list("a, b  c") == ["a", "b", "c"]


def test_normalize_value_and_wire_string_use_param_types() -> None:
    assert normalize_value("3.0", "int", default=0) == 3
    assert normalize_value("3.5", "float", default=0.0) == 3.5
    assert normalize_value("true", "bool", default=False) is True
    assert normalize_value("a,b", "multi_enum", default=[]) == ["a", "b"]
    assert wire_string(3.0, value_type="int") == "3"
