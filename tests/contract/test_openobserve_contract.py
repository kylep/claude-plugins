import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("openobserve")
pytestmark = [pytest.mark.contract, requires_env("O2_URL", "O2_TOKEN", "O2_ORG")]


def test_live_list_streams(monkeypatch, capsys):
    """The live /streams response still parses into the stream layout."""
    run_cli(mod, ["list-streams"], monkeypatch)
    out = capsys.readouterr().out
    # Either a header row or the explicit empty message — tolerant of empty data.
    assert "Name" in out or "No streams found." in out


def test_live_list_alerts(monkeypatch, capsys):
    """The live /alerts response still parses into the alert layout."""
    run_cli(mod, ["list-alerts"], monkeypatch)
    out = capsys.readouterr().out
    assert "alerts" in out.lower() or "No alerts configured." in out


def test_live_bounded_search(monkeypatch, capsys):
    """A small bounded search still returns the took/total summary line."""
    run_cli(
        mod,
        ["search-logs", "SELECT * FROM k8s_logs", "--start", "15m", "--limit", "1"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert "Query took" in out
    assert "total matches" in out
