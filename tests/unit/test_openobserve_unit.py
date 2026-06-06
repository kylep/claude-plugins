import pytest

from conftest import load_script

mod = load_script("openobserve")
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# parse_relative — relative duration strings -> seconds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_seconds",
    [
        ("30m", 30 * 60),
        ("1h", 3600),
        ("24h", 24 * 3600),
        ("7d", 7 * 86400),
        ("2w", 2 * 604800),
        ("  1H  ", 3600),  # trimmed + case-insensitive
        ("0m", 0),
    ],
)
def test_parse_relative_valid(text, expected_seconds):
    assert mod.parse_relative(text) == expected_seconds


@pytest.mark.parametrize("bad", ["", "h", "1", "1x", "1.5h", "-1h", "1 h", "abc"])
def test_parse_relative_invalid_exits(bad):
    with pytest.raises(SystemExit):
        mod.parse_relative(bad)


# ---------------------------------------------------------------------------
# to_microseconds — must be deterministic.  It reads time.time(); monkeypatch
# the module's time source so "now" is a fixed value.
# ---------------------------------------------------------------------------

# Fixed reference epoch (seconds) -> microseconds, for deterministic assertions.
FIXED_NOW_S = 1_700_000_000  # 2023-11-14T22:13:20Z
FIXED_NOW_US = FIXED_NOW_S * 1_000_000


@pytest.fixture
def frozen_time(monkeypatch):
    monkeypatch.setattr(mod.time, "time", lambda: float(FIXED_NOW_S))
    return FIXED_NOW_US


def test_to_microseconds_none_uses_default_ago(frozen_time):
    # Default "1h" ago = now - 3600s in microseconds.
    assert mod.to_microseconds(None) == frozen_time - 3600 * 1_000_000


def test_to_microseconds_none_custom_default(frozen_time):
    assert mod.to_microseconds(None, default_ago="15m") == frozen_time - 15 * 60 * 1_000_000


@pytest.mark.parametrize(
    "text,delta_seconds",
    [
        ("1h", 3600),
        ("15m", 15 * 60),
        ("7d", 7 * 86400),
        ("1H", 3600),  # case-insensitive relative branch
    ],
)
def test_to_microseconds_relative(frozen_time, text, delta_seconds):
    assert mod.to_microseconds(text) == frozen_time - delta_seconds * 1_000_000


def test_to_microseconds_unix_ms(frozen_time):
    # 13+ digit integer is treated as Unix milliseconds -> *1000 for micros.
    ms = "1700000000123"
    assert mod.to_microseconds(ms) == int(ms) * 1_000


def test_to_microseconds_iso_with_z(frozen_time):
    # 'Z' suffix is normalized to +00:00 (UTC).
    got = mod.to_microseconds("2023-11-14T22:13:20Z")
    assert got == FIXED_NOW_US


def test_to_microseconds_iso_naive_assumed_utc(frozen_time):
    # No tzinfo -> assumed UTC, same instant as the Z variant above.
    got = mod.to_microseconds("2023-11-14T22:13:20")
    assert got == FIXED_NOW_US


def test_to_microseconds_iso_with_offset(frozen_time):
    # Explicit +01:00 offset is one hour earlier in UTC.
    got = mod.to_microseconds("2023-11-14T23:13:20+01:00")
    assert got == FIXED_NOW_US


@pytest.mark.parametrize("bad", ["not-a-time", "2023-13-99", "tomorrow", "99h99"])
def test_to_microseconds_invalid_exits(frozen_time, bad):
    with pytest.raises(SystemExit):
        mod.to_microseconds(bad)


# ---------------------------------------------------------------------------
# search() body construction — pure SQL/time-range packing
# ---------------------------------------------------------------------------


def test_search_builds_query_body(monkeypatch):
    captured = {}

    def fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"hits": []}

    monkeypatch.setattr(mod, "http_post", fake_post)
    monkeypatch.setattr(mod, "get_org", lambda: "myorg")

    mod.search("SELECT * FROM k8s_logs", 100, 200, size=50)

    assert captured["path"] == "/api/myorg/_search"
    assert captured["body"] == {
        "query": {
            "sql": "SELECT * FROM k8s_logs",
            "start_time": 100,
            "end_time": 200,
            "from": 0,
            "size": 50,
        }
    }


def test_search_default_size(monkeypatch):
    captured = {}
    monkeypatch.setattr(mod, "http_post", lambda p, b: captured.update(body=b) or {})
    monkeypatch.setattr(mod, "get_org", lambda: "default")
    mod.search("SELECT 1", 1, 2)
    assert captured["body"]["query"]["size"] == 100
