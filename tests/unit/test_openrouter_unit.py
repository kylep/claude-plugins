import pytest

from conftest import load_script

mod = load_script("openrouter")
pytestmark = pytest.mark.unit


def test_format_dollars_pads_to_four_places():
    assert mod.format_dollars(0) == "$0.0000"
    assert mod.format_dollars(65.00187) == "$65.0019"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0", "free"),       # explicit zero string
        (0, "free"),          # numeric zero
        ("", "free"),         # unparseable -> ValueError -> free
        (None, "free"),       # None -> TypeError -> free
        ("0.000001", "$1.00"),
        (0.0000005, "$0.50"),
        ("0.00003", "$30.00"),
    ],
)
def test_per_million_tokens(value, expected):
    assert mod.per_million_tokens(value) == expected
