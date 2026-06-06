import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("google_news")
pytestmark = [pytest.mark.contract, requires_env("GNEWS_API_KEY")]


def test_live_search_returns_plausible_output(monkeypatch, capsys):
    """A live search call exits 0 and emits the expected header/wrapper."""
    run_cli(mod, ["search", "technology", "--max", "3"], monkeypatch)
    out = capsys.readouterr().out
    assert out.startswith('Found ')
    assert 'articles for "technology":' in out
    # Tolerant of zero results.
    assert '<news-data source="gnews-api">' in out or "No articles found." in out


def test_live_headlines_returns_plausible_output(monkeypatch, capsys):
    """A live top-headlines call exits 0 and emits the category header."""
    run_cli(mod, ["headlines", "--category", "technology", "--max", "3"], monkeypatch)
    out = capsys.readouterr().out
    assert "Top technology headlines:" in out
    assert '<news-data source="gnews-api">' in out or "No articles found." in out
