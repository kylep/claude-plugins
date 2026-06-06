import pytest

from conftest import http_error, load_script, patch_urlopen, run_cli

mod = load_script("openrouter")
pytestmark = pytest.mark.integration

KEY_PAYLOAD = {
    "data": {
        "label": "test-key",
        "is_free_tier": False,
        "usage": 65.0,
        "usage_daily": 0,
        "usage_weekly": 0,
        "usage_monthly": 1.5,
        "limit": 200,
        "limit_remaining": 150,
    }
}


def _models(n):
    return {
        "data": [
            {
                "id": f"vendor/model-{i}",
                "name": f"Model {i}",
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                "context_length": 128000,
            }
            for i in range(n)
        ]
    }


def test_get_usage_renders_and_authorizes(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    fake = patch_urlopen(monkeypatch, mod, [KEY_PAYLOAD])
    run_cli(mod, ["get-usage"], monkeypatch)

    out = capsys.readouterr().out
    assert "Total:  $65.0000" in out
    assert "Remaining: $150.0000" in out
    req = fake.last_request
    assert req.full_url == "https://openrouter.ai/api/v1/key"
    assert req.get_header("Authorization") == "Bearer sk-test"


def test_model_pricing_formats_per_million(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    patch_urlopen(monkeypatch, mod, [_models(1)])
    run_cli(mod, ["get-model-pricing"], monkeypatch)

    out = capsys.readouterr().out
    assert "vendor/model-0" in out
    assert "Prompt: $1.00/M tokens" in out
    assert "Completion: $2.00/M tokens" in out
    assert "Context: 128k" in out


def test_model_pricing_filters_by_term(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    payload = _models(3)
    payload["data"][1]["id"] = "openai/gpt-4"
    patch_urlopen(monkeypatch, mod, [payload])
    run_cli(mod, ["get-model-pricing", "--model", "gpt"], monkeypatch)

    out = capsys.readouterr().out
    assert "openai/gpt-4" in out
    assert "vendor/model-0" not in out


def test_model_pricing_caps_at_twenty(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    patch_urlopen(monkeypatch, mod, [_models(25)])
    run_cli(mod, ["get-model-pricing"], monkeypatch)

    out = capsys.readouterr().out
    assert "... and 5 more" in out


def test_http_error_exits(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    patch_urlopen(monkeypatch, mod, [http_error(401, {"error": "unauthorized"})])
    with pytest.raises(SystemExit):
        run_cli(mod, ["get-usage"], monkeypatch)


def test_missing_key_exits_before_network(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # No urlopen patch: if it tried the network the test would error, not exit.
    with pytest.raises(SystemExit):
        run_cli(mod, ["get-usage"], monkeypatch)
