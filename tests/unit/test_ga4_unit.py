import pytest

from conftest import load_script

mod = load_script("ga4")
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Property-id resolution precedence: arg over env over unset -> error
# ---------------------------------------------------------------------------


def test_property_arg_wins_over_env(monkeypatch):
    monkeypatch.setenv("GA4_PROPERTY_ID", "999999")
    assert mod.get_property("123456") == "properties/123456"


def test_property_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("GA4_PROPERTY_ID", "999999")
    assert mod.get_property("") == "properties/999999"


def test_property_unset_exits(monkeypatch):
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    with pytest.raises(SystemExit):
        mod.get_property("")


def test_property_blank_env_exits(monkeypatch):
    monkeypatch.setenv("GA4_PROPERTY_ID", "   ")
    with pytest.raises(SystemExit):
        mod.get_property("")


def test_property_already_prefixed_left_alone(monkeypatch):
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    assert mod.get_property("properties/777") == "properties/777"


def test_property_strips_whitespace(monkeypatch):
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    assert mod.get_property("  123456  ") == "properties/123456"


def test_property_env_strips_whitespace(monkeypatch):
    monkeypatch.setenv("GA4_PROPERTY_ID", "  555  ")
    assert mod.get_property("") == "properties/555"


# ---------------------------------------------------------------------------
# split_csv
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("activeUsers,sessions", ["activeUsers", "sessions"]),
        (" activeUsers , sessions ", ["activeUsers", "sessions"]),
        ("activeUsers,,sessions", ["activeUsers", "sessions"]),  # blank dropped
        ("", []),
        (",", []),
        ("   ", []),
        ("activeUsers", ["activeUsers"]),
    ],
)
def test_split_csv(value, expected):
    assert mod.split_csv(value) == expected


# ---------------------------------------------------------------------------
# print_rows row/number rendering
# ---------------------------------------------------------------------------


class _Val:
    def __init__(self, value):
        self.value = value


class _Row:
    def __init__(self, dims, mets):
        self.dimension_values = [_Val(v) for v in dims]
        self.metric_values = [_Val(v) for v in mets]


def test_print_rows_no_data(capsys):
    mod.print_rows([], ["date"], ["activeUsers"])
    out = capsys.readouterr().out
    assert out.strip() == "No data."


def test_print_rows_renders_headers_and_values(capsys):
    rows = [
        _Row(["20240101", "US"], ["10", "5"]),
        _Row(["20240102", "CA"], ["7", "3"]),
    ]
    mod.print_rows(rows, ["date", "country"], ["activeUsers", "sessions"])
    out = capsys.readouterr().out

    # Header line contains all column names.
    assert "date" in out
    assert "country" in out
    assert "activeUsers" in out
    assert "sessions" in out
    # Values rendered in order: dimensions then metrics.
    assert "20240101" in out
    assert "US" in out
    assert "20240102" in out
    assert "CA" in out
    # A separator dashes line exists.
    assert "---" in out


def test_print_rows_columns_padded_to_min_width(capsys):
    # Header shorter than 20 chars is padded to a 20-wide column.
    mod.print_rows([_Row(["x"], ["1"])], ["d"], ["m"])
    lines = capsys.readouterr().out.splitlines()
    header = lines[0]
    # Two columns each min-width 20 joined by two spaces -> >= 42 chars.
    assert len(header) >= 42
