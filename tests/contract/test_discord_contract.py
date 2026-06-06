import re

import pytest

from conftest import load_script, requires_env, run_cli

mod = load_script("discord")
pytestmark = [pytest.mark.contract, requires_env("DISCORD_BOT_TOKEN")]


def test_live_list_guilds(monkeypatch, capsys):
    """The bot token authenticates and /users/@me/guilds parses (exit 0)."""
    run_cli(mod, ["list-guilds"], monkeypatch)
    # No exception == exit 0. Output is either guild lines or the empty notice.
    out = capsys.readouterr().out
    assert out  # something was printed


@requires_env("DISCORD_GUILD_ID")
def test_live_list_channels(monkeypatch, capsys):
    """list-channels against the configured guild returns without error."""
    run_cli(mod, ["list-channels"], monkeypatch)
    out = capsys.readouterr().out
    assert out


@requires_env("DISCORD_TEST_CHANNEL_ID")
def test_live_send_and_delete(monkeypatch, capsys):
    """Send a message via the CLI, capture its id, then delete it via the CLI.

    cmd_send_message prints `Sent message <id> in #<channel>`; we parse the id
    from stdout and tear it down in a finally block so cleanup always runs.
    """
    import os

    channel = os.environ["DISCORD_TEST_CHANNEL_ID"]
    run_cli(
        mod,
        ["send-message", channel, "pai-tools contract test message"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    match = re.search(r"Sent message (\d+) in", out)
    assert match, f"could not parse message id from: {out!r}"
    message_id = match.group(1)

    try:
        assert message_id  # send succeeded
    finally:
        run_cli(mod, ["delete-message", channel, message_id], monkeypatch)
        cleanup_out = capsys.readouterr().out
        assert f"Deleted message {message_id}" in cleanup_out
