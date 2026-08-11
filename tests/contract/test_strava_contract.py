import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("strava")

# Read-only, live. Needs the app credentials + a refresh token so the script can
# mint a fresh access token (seed access token may already be expired). Auto-skips
# when any are absent.
pytestmark = [
    pytest.mark.contract,
    requires_env("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN"),
]


def test_live_athlete_has_expected_fields(monkeypatch, capsys):
    """The live /athlete response still carries the id/name fields the script renders."""
    run_cli(mod, ["athlete", "--json"], monkeypatch)
    out = capsys.readouterr().out
    import json

    data = json.loads(out)
    assert "id" in data
    assert "username" in data or "firstname" in data


def test_live_activities_returns_list(monkeypatch, capsys):
    """The live /athlete/activities response still parses into the list layout.

    Skips if the granted token lacks the activity:read scope (a setup issue,
    not an API-contract failure).
    """
    try:
        run_cli(mod, ["activities", "--per-page", "1", "--json"], monkeypatch)
    except SystemExit as e:
        if "activity:read" in str(e) or "activity_read" in str(e):
            pytest.skip("token lacks activity:read scope — re-authorize to enable")
        raise
    out = capsys.readouterr().out
    import json

    data = json.loads(out)
    assert isinstance(data, list)
    if data:
        assert "id" in data[0]
        assert "distance" in data[0]
