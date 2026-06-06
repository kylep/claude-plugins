import shutil

import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("bitwarden")
pytestmark = [
    pytest.mark.contract,
    requires_env("BW_SESSION"),
    pytest.mark.skipif(
        shutil.which("bw") is None,
        reason="bw CLI not on PATH",
    ),
]


def test_live_status_returns_json(monkeypatch, capsys):
    """`bw status` still parses and prints; vault should be reachable."""
    run_cli(mod, ["status"], monkeypatch)
    out = capsys.readouterr().out
    # bw status emits a JSON blob with a "status" field.
    assert "status" in out


def test_live_list_items_runs_readonly(monkeypatch, capsys):
    """Read-only listing succeeds and renders a plausible summary."""
    run_cli(mod, ["list-items"], monkeypatch)
    out = capsys.readouterr().out
    assert "No items found." in out or "item(s):" in out
