import pytest

from conftest import load_script

mod = load_script("linear")
pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "—"),       # 0 maps to default ("None" semantics), default returned
        (1, "Urgent"),
        (2, "High"),
        (3, "Medium"),
        (4, "Low"),
    ],
)
def test_priority_name_boundaries(value, expected):
    assert mod.priority_name(value) == expected


def test_priority_name_zero_uses_custom_default():
    assert mod.priority_name(0, default="None") == "None"


@pytest.mark.parametrize(
    "value",
    [
        5,            # out of range high
        -1,           # negative
        None,         # not an int
        "2",          # string, not int
        2.0,          # float, not int
        True,         # bool is int-ish but value 1 -> "Urgent"; keep separate below
    ],
)
def test_priority_name_out_of_range_returns_default(value):
    if value is True:
        # bool True is an int with value 1 -> "Urgent"; verify that explicitly.
        assert mod.priority_name(value) == "Urgent"
    else:
        assert mod.priority_name(value) == "—"


def test_priority_names_table():
    assert mod.PRIORITY_NAMES == ("None", "Urgent", "High", "Medium", "Low")
