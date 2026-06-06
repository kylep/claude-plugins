import pytest

from conftest import load_script

mod = load_script("discord")
pytestmark = pytest.mark.unit


def test_check_len_allows_max_length():
    # Exactly MAX_MESSAGE_LEN (2000) is permitted: no exception.
    assert mod.MAX_MESSAGE_LEN == 2000
    mod.check_len("x" * mod.MAX_MESSAGE_LEN)


def test_check_len_allows_empty():
    mod.check_len("")


def test_check_len_rejects_over_limit():
    with pytest.raises(SystemExit):
        mod.check_len("x" * (mod.MAX_MESSAGE_LEN + 1))


def test_get_token_exits_when_unset(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        mod.get_token()


def test_get_token_returns_value(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "abc")
    assert mod.get_token() == "abc"
