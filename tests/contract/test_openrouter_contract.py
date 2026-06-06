import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("openrouter")
pytestmark = [pytest.mark.contract, requires_env("OPENROUTER_API_KEY")]


def test_live_usage_has_expected_fields(monkeypatch, capsys):
    """The live /key response still carries the usage fields the script renders."""
    run_cli(mod, ["get-usage"], monkeypatch)
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "Total:" in out
    assert "$" in out


def test_live_pricing_returns_models(monkeypatch, capsys):
    """The live /models response still parses into the pricing layout."""
    run_cli(mod, ["get-model-pricing", "--model", "gpt"], monkeypatch)
    out = capsys.readouterr().out
    assert "/M tokens" in out or out.startswith("No models")
