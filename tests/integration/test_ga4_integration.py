import sys
import types

import pytest

from conftest import load_script, run_cli

mod = load_script("ga4")
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fake google.analytics.data_v1beta module tree
#
# The script imports the SDK lazily inside its functions:
#   from google.analytics.data_v1beta import BetaAnalyticsDataClient
#   from google.analytics.data_v1beta.types import (DateRange, Dimension,
#       Metric, RunRealtimeReportRequest, RunReportRequest)
# We satisfy those imports by injecting fake modules into sys.modules with
# monkeypatch.setitem (auto-removed after each test).
# ---------------------------------------------------------------------------


class _Val:
    def __init__(self, value):
        self.value = value


class _Header:
    def __init__(self, name):
        self.name = name


class _Row:
    def __init__(self, dims, mets):
        self.dimension_values = [_Val(v) for v in dims]
        self.metric_values = [_Val(v) for v in mets]


class _Response:
    """Stand-in for a RunReport / RunRealtimeReport response."""

    def __init__(self, dim_headers, met_headers, rows):
        self.dimension_headers = [_Header(h) for h in dim_headers]
        self.metric_headers = [_Header(h) for h in met_headers]
        self.rows = [_Row(d, m) for d, m in rows]


# Simple value-holder request/field classes that record kwargs.
def _kw_class():
    class _C:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    return _C


def _make_fake_sdk(report_response, realtime_response):
    """Build the fake module tree and return (modules, client_holder).

    client_holder is a dict that, after a command runs, holds the request
    object passed to run_report / run_realtime_report so tests can assert on
    property / date_ranges / metrics / dimensions / limit.
    """
    captured = {}

    Metric = _kw_class()
    Dimension = _kw_class()
    DateRange = _kw_class()
    RunReportRequest = _kw_class()
    RunRealtimeReportRequest = _kw_class()

    class BetaAnalyticsDataClient:
        def __init__(self, *a, **k):
            captured["client_inited"] = True

        def run_report(self, request):
            captured["run_report_request"] = request
            return report_response

        def run_realtime_report(self, request):
            captured["run_realtime_request"] = request
            return realtime_response

    google = types.ModuleType("google")
    google.__path__ = []  # mark as package
    analytics = types.ModuleType("google.analytics")
    analytics.__path__ = []
    data = types.ModuleType("google.analytics.data_v1beta")
    data.__path__ = []
    data.BetaAnalyticsDataClient = BetaAnalyticsDataClient
    typesmod = types.ModuleType("google.analytics.data_v1beta.types")
    typesmod.DateRange = DateRange
    typesmod.Dimension = Dimension
    typesmod.Metric = Metric
    typesmod.RunRealtimeReportRequest = RunRealtimeReportRequest
    typesmod.RunReportRequest = RunReportRequest

    google.analytics = analytics
    analytics.data_v1beta = data
    data.types = typesmod

    modules = {
        "google": google,
        "google.analytics": analytics,
        "google.analytics.data_v1beta": data,
        "google.analytics.data_v1beta.types": typesmod,
    }
    return modules, captured


def _install(monkeypatch, modules):
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def _with_creds(monkeypatch):
    monkeypatch.setenv("GA4_PROPERTY_ID", "123456")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/fake-key.json")


# ---------------------------------------------------------------------------
# run-report
# ---------------------------------------------------------------------------


def test_run_report_renders_and_calls_client(monkeypatch, capsys):
    _with_creds(monkeypatch)
    resp = _Response(
        dim_headers=["date", "country"],
        met_headers=["activeUsers", "sessions"],
        rows=[(["20240101", "US"], ["10", "5"])],
    )
    modules, captured = _make_fake_sdk(resp, None)
    _install(monkeypatch, modules)

    run_cli(
        mod,
        [
            "run-report",
            "--metrics",
            "activeUsers,sessions",
            "--dimensions",
            "date,country",
            "--start",
            "7daysAgo",
            "--end",
            "today",
            "--limit",
            "10",
        ],
        monkeypatch,
    )

    out = capsys.readouterr().out
    assert "GA4 report (7daysAgo → today), 1 rows:" in out
    assert "date" in out and "country" in out
    assert "activeUsers" in out and "sessions" in out
    assert "20240101" in out and "US" in out

    req = captured["run_report_request"]
    assert req.property == "properties/123456"
    assert req.limit == 10
    assert [d.start_date for d in req.date_ranges] == ["7daysAgo"]
    assert [d.end_date for d in req.date_ranges] == ["today"]
    assert [m.name for m in req.metrics] == ["activeUsers", "sessions"]
    assert [d.name for d in req.dimensions] == ["date", "country"]


def test_run_report_defaults_dates(monkeypatch, capsys):
    _with_creds(monkeypatch)
    resp = _Response(["date"], ["activeUsers"], rows=[])
    modules, captured = _make_fake_sdk(resp, None)
    _install(monkeypatch, modules)

    run_cli(mod, ["run-report", "--metrics", "activeUsers"], monkeypatch)

    out = capsys.readouterr().out
    # No rows -> "No data." and default date window in header.
    assert "GA4 report (28daysAgo → yesterday), 0 rows:" in out
    assert "No data." in out
    req = captured["run_report_request"]
    assert [d.start_date for d in req.date_ranges] == ["28daysAgo"]
    assert [d.end_date for d in req.date_ranges] == ["yesterday"]
    assert req.dimensions == []  # no --dimensions


def test_run_report_property_arg_overrides_env(monkeypatch, capsys):
    _with_creds(monkeypatch)  # env says 123456
    resp = _Response(["date"], ["activeUsers"], rows=[])
    modules, captured = _make_fake_sdk(resp, None)
    _install(monkeypatch, modules)

    run_cli(
        mod,
        ["run-report", "--metrics", "activeUsers", "--property", "888"],
        monkeypatch,
    )
    capsys.readouterr()
    assert captured["run_report_request"].property == "properties/888"


# ---------------------------------------------------------------------------
# realtime
# ---------------------------------------------------------------------------


def test_realtime_renders_and_calls_client(monkeypatch, capsys):
    _with_creds(monkeypatch)
    resp = _Response(
        dim_headers=["country"],
        met_headers=["activeUsers"],
        rows=[(["US"], ["42"]), (["CA"], ["7"])],
    )
    modules, captured = _make_fake_sdk(None, resp)
    _install(monkeypatch, modules)

    run_cli(
        mod,
        [
            "realtime",
            "--metrics",
            "activeUsers",
            "--dimensions",
            "country",
            "--limit",
            "5",
        ],
        monkeypatch,
    )

    out = capsys.readouterr().out
    assert "GA4 realtime, 2 rows:" in out
    assert "country" in out and "activeUsers" in out
    assert "US" in out and "42" in out
    assert "CA" in out and "7" in out

    req = captured["run_realtime_request"]
    assert req.property == "properties/123456"
    assert req.limit == 5
    assert [m.name for m in req.metrics] == ["activeUsers"]
    assert [d.name for d in req.dimensions] == ["country"]
    # Realtime request has no date_ranges attribute.
    assert not hasattr(req, "date_ranges")


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_missing_property_exits(monkeypatch):
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/fake-key.json")
    resp = _Response(["date"], ["activeUsers"], rows=[])
    modules, _ = _make_fake_sdk(resp, None)
    _install(monkeypatch, modules)

    with pytest.raises(SystemExit):
        run_cli(mod, ["run-report", "--metrics", "activeUsers"], monkeypatch)


def test_missing_credentials_exits(monkeypatch):
    monkeypatch.setenv("GA4_PROPERTY_ID", "123456")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    resp = _Response(["date"], ["activeUsers"], rows=[])
    modules, _ = _make_fake_sdk(resp, None)
    _install(monkeypatch, modules)

    with pytest.raises(SystemExit):
        run_cli(mod, ["run-report", "--metrics", "activeUsers"], monkeypatch)
