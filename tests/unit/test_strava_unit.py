import pytest

from conftest import load_script

mod = load_script("strava")
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Token expiry
# ---------------------------------------------------------------------------


def test_token_expired_when_past():
    # now=1000, buffer=60 -> anything <= 1060 is "expired"
    assert mod.is_token_expired(1000, now=1000) is True
    assert mod.is_token_expired(1059, now=1000) is True
    assert mod.is_token_expired(1060, now=1000) is True  # boundary is inclusive


def test_token_valid_when_future():
    assert mod.is_token_expired(1061, now=1000) is False
    assert mod.is_token_expired(9999, now=1000) is False


def test_token_expired_on_bad_value():
    assert mod.is_token_expired(None, now=1000) is True
    assert mod.is_token_expired("nope", now=1000) is True


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "meters,expected",
    [(1000, "1.00 km"), (5432, "5.43 km"), (0, "0.00 km")],
)
def test_fmt_distance(meters, expected):
    assert mod.fmt_distance(meters) == expected


def test_fmt_distance_bad():
    assert mod.fmt_distance(None) == "—"
    assert mod.fmt_distance("x") == "—"


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "0:00"),
        (59, "0:59"),
        (60, "1:00"),
        (125, "2:05"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
    ],
)
def test_fmt_duration(seconds, expected):
    assert mod.fmt_duration(seconds) == expected


def test_fmt_duration_bad():
    assert mod.fmt_duration(None) == "—"


# ---------------------------------------------------------------------------
# Pagination clamp
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [(1, 1), (30, 30), (200, 200), (500, 200), (0, 1), (-5, 1)],
)
def test_clamp_per_page(value, expected):
    assert mod.clamp_per_page(value) == expected


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------


def test_parse_time_none():
    assert mod.parse_time(None) is None


def test_parse_time_epoch_passthrough():
    assert mod.parse_time("1700000000") == 1700000000


def test_parse_time_iso_date():
    # 2021-01-01 UTC midnight
    assert mod.parse_time("2021-01-01") == 1609459200


def test_parse_time_invalid_exits():
    with pytest.raises(SystemExit):
        mod.parse_time("not-a-date")


# ---------------------------------------------------------------------------
# Bounds parsing
# ---------------------------------------------------------------------------


def test_parse_bounds_ok():
    assert mod.parse_bounds("1.0,2.0,3.0,4.0") == "1.0,2.0,3.0,4.0"
    assert mod.parse_bounds(" 1, 2 , 3, 4 ") == "1,2,3,4"


def test_parse_bounds_wrong_count_exits():
    with pytest.raises(SystemExit):
        mod.parse_bounds("1,2,3")


def test_parse_bounds_non_numeric_exits():
    with pytest.raises(SystemExit):
        mod.parse_bounds("1,2,3,x")


# ---------------------------------------------------------------------------
# Stream summary
# ---------------------------------------------------------------------------


def test_stream_summary_key_by_type():
    data = {
        "time": {"data": [0, 1, 2], "series_type": "distance"},
        "heartrate": {"data": [100, 110]},
    }
    lines = mod.stream_summary(data)
    assert "  time: 3 points" in lines
    assert "  heartrate: 2 points" in lines


def test_stream_summary_list_form():
    data = [{"type": "time", "data": [0, 1]}, {"type": "watts", "data": [200]}]
    lines = mod.stream_summary(data)
    assert "  time: 2 points" in lines
    assert "  watts: 1 points" in lines


def test_stream_summary_empty():
    assert mod.stream_summary({}) == []


# ---------------------------------------------------------------------------
# Dispatch table wiring
# ---------------------------------------------------------------------------


def test_every_subcommand_has_a_handler():
    parser = mod.build_parser()
    # Pull the registered subcommand names from the subparsers action.
    subactions = [
        a for a in parser._actions if isinstance(a, mod.argparse._SubParsersAction)
    ]
    names = set(subactions[0].choices.keys())
    assert names == set(mod.DISPATCH.keys())
