import argparse
from datetime import date, datetime, timezone

import pytest

from conftest import load_script, run_cli

mod = load_script("gsc")
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# resolve_site_url — site-url/path resolution from env / argument
# ---------------------------------------------------------------------------


def test_resolve_site_url_prefers_explicit_arg(monkeypatch):
    monkeypatch.setattr(mod, "SITE_URL_ENV", "https://env.example/")
    assert mod.resolve_site_url("https://arg.example/") == "https://arg.example/"


def test_resolve_site_url_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(mod, "SITE_URL_ENV", "https://env.example/")
    assert mod.resolve_site_url("") == "https://env.example/"


def test_resolve_site_url_strips_whitespace(monkeypatch):
    monkeypatch.setattr(mod, "SITE_URL_ENV", "")
    assert mod.resolve_site_url("  https://arg.example/  ") == "https://arg.example/"


def test_resolve_site_url_exits_when_unset(monkeypatch):
    monkeypatch.setattr(mod, "SITE_URL_ENV", "")
    with pytest.raises(SystemExit) as exc:
        mod.resolve_site_url("")
    assert "No site URL" in str(exc.value)


def test_resolve_site_url_blank_arg_blank_env_exits(monkeypatch):
    monkeypatch.setattr(mod, "SITE_URL_ENV", "   ")
    with pytest.raises(SystemExit):
        mod.resolve_site_url("   ")


# ---------------------------------------------------------------------------
# Helpers for exercising the date-range + rendering logic without google libs.
# We stub get_service() with a fake whose query().execute() captures the body
# and returns a canned payload, and we pin "today" via a fake datetime so the
# default date range is deterministic.
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, store, payload):
        self._store = store
        self._payload = payload

    def query(self, siteUrl, body):
        self._store["siteUrl"] = siteUrl
        self._store["body"] = body
        return self

    def execute(self):
        return self._payload


class _FakeService:
    def __init__(self, store, payload):
        self._q = _FakeQuery(store, payload)

    def searchanalytics(self):
        return self._q


def _pin_today(monkeypatch, ref: date):
    """Freeze datetime.now(timezone.utc).date() to a fixed reference date."""

    class _FrozenDatetime:
        @staticmethod
        def now(tz=None):
            # Return a real datetime whose .date() is the reference date.
            return datetime(ref.year, ref.month, ref.day, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(mod, "datetime", _FrozenDatetime)


def _install_fake_service(monkeypatch, payload):
    store: dict = {}
    monkeypatch.setattr(mod, "get_service", lambda: _FakeService(store, payload))
    return store


def _sa_args(**overrides):
    base = dict(
        start=None,
        end=None,
        dimensions="query",
        limit=25,
        page_filter="",
        query_filter="",
        site="https://site.example/",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# Date-range computation (default = today-28 .. today-3)
# ---------------------------------------------------------------------------


def test_default_date_range_is_28_to_3_days_back(monkeypatch):
    _pin_today(monkeypatch, date(2026, 6, 5))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args())
    # 2026-06-05 minus 28 days -> 2026-05-08 ; minus 3 days -> 2026-06-02
    assert store["body"]["startDate"] == "2026-05-08"
    assert store["body"]["endDate"] == "2026-06-02"


def test_explicit_dates_override_defaults(monkeypatch):
    _pin_today(monkeypatch, date(2026, 6, 5))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args(start="2026-01-01", end="2026-01-31"))
    assert store["body"]["startDate"] == "2026-01-01"
    assert store["body"]["endDate"] == "2026-01-31"


def test_date_range_crosses_month_boundary(monkeypatch):
    _pin_today(monkeypatch, date(2026, 1, 10))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args())
    assert store["body"]["startDate"] == "2025-12-13"
    assert store["body"]["endDate"] == "2026-01-07"


# ---------------------------------------------------------------------------
# Body construction (dimensions, limit clamp, filters, dataState)
# ---------------------------------------------------------------------------


def test_dimensions_parsed_and_trimmed(monkeypatch):
    _pin_today(monkeypatch, date(2026, 6, 5))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args(dimensions=" query , page "))
    assert store["body"]["dimensions"] == ["query", "page"]


def test_empty_dimensions_default_to_query(monkeypatch):
    _pin_today(monkeypatch, date(2026, 6, 5))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args(dimensions=" , "))
    assert store["body"]["dimensions"] == ["query"]


def test_invalid_dimension_exits(monkeypatch):
    _pin_today(monkeypatch, date(2026, 6, 5))
    _install_fake_service(monkeypatch, {"rows": []})
    with pytest.raises(SystemExit) as exc:
        mod.cmd_search_analytics(_sa_args(dimensions="query,bogus"))
    assert "bogus" in str(exc.value)


@pytest.mark.parametrize(
    "limit,expected",
    [
        (0, 1),          # clamped up to minimum 1
        (-5, 1),
        (25, 25),
        (25000, 25000),
        (999999, 25000),  # clamped down to max
    ],
)
def test_limit_is_clamped(monkeypatch, limit, expected):
    _pin_today(monkeypatch, date(2026, 6, 5))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args(limit=limit))
    assert store["body"]["rowLimit"] == expected


def test_data_state_is_all(monkeypatch):
    _pin_today(monkeypatch, date(2026, 6, 5))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args())
    assert store["body"]["dataState"] == "all"


def test_page_and_query_filters_build_filter_group(monkeypatch):
    _pin_today(monkeypatch, date(2026, 6, 5))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args(page_filter="/blog", query_filter="claude"))
    groups = store["body"]["dimensionFilterGroups"]
    assert groups == [
        {
            "filters": [
                {"dimension": "page", "operator": "contains", "expression": "/blog"},
                {
                    "dimension": "query",
                    "operator": "contains",
                    "expression": "claude",
                },
            ]
        }
    ]


def test_no_filters_omits_filter_group(monkeypatch):
    _pin_today(monkeypatch, date(2026, 6, 5))
    store = _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args())
    assert "dimensionFilterGroups" not in store["body"]


# ---------------------------------------------------------------------------
# Row / number rendering
# ---------------------------------------------------------------------------


def test_empty_rows_prints_no_data_message(monkeypatch, capsys):
    _pin_today(monkeypatch, date(2026, 6, 5))
    _install_fake_service(monkeypatch, {"rows": []})
    mod.cmd_search_analytics(_sa_args())
    out = capsys.readouterr().out
    assert "No search analytics data for 2026-05-08 to 2026-06-02." in out


def test_row_rendering_formats_ctr_and_position(monkeypatch, capsys):
    _pin_today(monkeypatch, date(2026, 6, 5))
    payload = {
        "rows": [
            {
                "keys": ["claude code"],
                "clicks": 12,
                "impressions": 340,
                "ctr": 0.035294,
                "position": 4.27,
            }
        ]
    }
    _install_fake_service(monkeypatch, payload)
    mod.cmd_search_analytics(_sa_args())
    out = capsys.readouterr().out
    # Header reflects capitalized dimension + the canned range and row count.
    assert "Search analytics for https://site.example/ (2026-05-08 to 2026-06-02), 1 rows:" in out
    assert "Query" in out
    assert "claude code" in out
    # ctr 0.035294 -> 3.5% (".1%"), position 4.27 -> 4.3 (".1f")
    assert "3.5%" in out
    assert "4.3" in out


def test_row_rendering_defaults_missing_metrics_to_zero(monkeypatch, capsys):
    _pin_today(monkeypatch, date(2026, 6, 5))
    payload = {"rows": [{"keys": ["bare"]}]}
    _install_fake_service(monkeypatch, payload)
    mod.cmd_search_analytics(_sa_args())
    out = capsys.readouterr().out
    assert "bare" in out
    assert "0.0%" in out  # ctr default 0 -> 0.0%
