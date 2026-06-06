import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("ga4")
pytestmark = [
    pytest.mark.contract,
    requires_env("GA4_PROPERTY_ID", "GOOGLE_APPLICATION_CREDENTIALS"),
]

def _require_sdk():
    # Checked inside each test (not at module scope) so default non-contract
    # runs deselect by marker instead of reporting a collection-time skip.
    pytest.importorskip(
        "google.analytics.data_v1beta",
        reason="google-analytics-data not installed",
    )


def test_live_run_report(monkeypatch, capsys):
    """A read-only historical report still parses into the rendered layout."""
    _require_sdk()
    run_cli(
        mod,
        ["run-report", "--metrics", "activeUsers", "--dimensions", "date", "--limit", "5"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert "GA4 report" in out
    assert "activeUsers" in out or "No data." in out


def test_live_realtime(monkeypatch, capsys):
    """A read-only realtime report still parses into the rendered layout."""
    _require_sdk()
    run_cli(
        mod,
        ["realtime", "--metrics", "activeUsers", "--limit", "5"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert "GA4 realtime" in out
    assert "activeUsers" in out or "No data." in out
