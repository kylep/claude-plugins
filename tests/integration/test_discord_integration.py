import json

import pytest

from conftest import (
    FakeResponse,
    http_error,
    load_script,
    patch_urlopen,
    run_cli,
)

mod = load_script("discord")
pytestmark = pytest.mark.integration

BASE = "https://discord.com/api/v10"


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")


def _router(routes):
    """Build a callable for FakeUrlopen that branches on (method, full_url).

    `routes` maps (method, full_url) -> payload / FakeResponse / Exception.
    Paths are matched ignoring any query string.
    """

    def handler(req):
        url = req.full_url.split("?", 1)[0]
        key = (req.method, url)
        if key not in routes:
            raise AssertionError(f"unexpected request: {req.method} {req.full_url}")
        result = routes[key]
        return result

    return handler


# ---------------------------------------------------------------------------
# request() plumbing
# ---------------------------------------------------------------------------


def test_request_builds_authorized_request(monkeypatch):
    fake = patch_urlopen(
        monkeypatch, mod, _router({("GET", f"{BASE}/ping"): {"ok": True}})
    )
    result = mod.request("GET", "/ping")
    assert result == {"ok": True}
    req = fake.last_request
    assert req.full_url == f"{BASE}/ping"
    assert req.method == "GET"
    assert req.get_header("Authorization") == "Bot test-token"
    assert req.get_header("User-agent") == mod.USER_AGENT
    assert req.get_header("Content-type") == "application/json"


def test_request_204_returns_none(monkeypatch):
    patch_urlopen(
        monkeypatch,
        mod,
        _router({("DELETE", f"{BASE}/x"): FakeResponse(None, status=204)}),
    )
    assert mod.request("DELETE", "/x") is None


def test_request_serializes_body_and_params(monkeypatch):
    fake = patch_urlopen(
        monkeypatch, mod, _router({("POST", f"{BASE}/thing"): {"id": "1"}})
    )
    mod.request("POST", "/thing", body={"a": 1}, params={"limit": 5})
    req = fake.last_request
    assert req.full_url == f"{BASE}/thing?limit=5"
    assert json.loads(req.data.decode("utf-8")) == {"a": 1}


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def test_list_guilds(monkeypatch, capsys):
    payload = [{"id": "10", "name": "Alpha"}, {"id": "20", "name": "Beta"}]
    fake = patch_urlopen(
        monkeypatch, mod, _router({("GET", f"{BASE}/users/@me/guilds"): payload})
    )
    run_cli(mod, ["list-guilds"], monkeypatch)
    out = capsys.readouterr().out
    assert "- Alpha  (id: 10)" in out
    assert "- Beta  (id: 20)" in out
    assert fake.last_request.full_url == f"{BASE}/users/@me/guilds"


def test_list_guilds_empty(monkeypatch, capsys):
    patch_urlopen(monkeypatch, mod, _router({("GET", f"{BASE}/users/@me/guilds"): []}))
    run_cli(mod, ["list-guilds"], monkeypatch)
    assert "has not joined any servers" in capsys.readouterr().out


def test_list_channels_filters_and_sorts(monkeypatch, capsys):
    # type 0 = text, 5 = announcement (both shown); 2 = voice, 4 = category (hidden).
    channels = [
        {"id": "c1", "name": "general", "type": 0, "position": 2},
        {"id": "c2", "name": "voice", "type": 2, "position": 0},
        {"id": "c3", "name": "news", "type": 5, "position": 1},
        {"id": "c4", "name": "category", "type": 4, "position": 3},
        {"id": "c5", "name": "first", "type": 0, "position": 0},
    ]
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router({("GET", f"{BASE}/guilds/G1/channels"): channels}),
    )
    run_cli(mod, ["list-channels", "--guild-id", "G1"], monkeypatch)
    out = capsys.readouterr().out
    # voice + category excluded
    assert "voice" not in out
    assert "category" not in out
    # remaining sorted by position: first(0), news(1), general(2)
    lines = [ln for ln in out.splitlines() if ln.startswith("- #")]
    assert lines == ["- #first  (id: c5)", "- #news  (id: c3)", "- #general  (id: c1)"]
    assert fake.last_request.full_url == f"{BASE}/guilds/G1/channels"


def test_list_channels_uses_env_default(monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_GUILD_ID", "ENVG")
    patch_urlopen(
        monkeypatch,
        mod,
        _router({("GET", f"{BASE}/guilds/ENVG/channels"): []}),
    )
    run_cli(mod, ["list-channels"], monkeypatch)
    assert "No text channels found." in capsys.readouterr().out


def test_list_channels_requires_guild(monkeypatch):
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-channels"], monkeypatch)


def test_get_channel_info(monkeypatch, capsys):
    payload = {
        "id": "CH1",
        "name": "general",
        "type": 0,
        "topic": "hi there",
        "guild_id": "G1",
    }
    fake = patch_urlopen(
        monkeypatch, mod, _router({("GET", f"{BASE}/channels/CH1"): payload})
    )
    run_cli(mod, ["get-channel-info", "CH1"], monkeypatch)
    out = capsys.readouterr().out
    assert "Name: #general" in out
    assert "ID: CH1" in out
    assert "Topic: hi there" in out
    assert "Guild ID: G1" in out
    assert fake.last_request.full_url == f"{BASE}/channels/CH1"


def test_send_message(monkeypatch, capsys):
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router({("POST", f"{BASE}/channels/CH1/messages"): {"id": "MSG1"}}),
    )
    run_cli(mod, ["send-message", "CH1", "hello world"], monkeypatch)
    out = capsys.readouterr().out
    assert "Sent message MSG1 in #CH1" in out
    req = fake.last_request
    assert req.method == "POST"
    assert req.full_url == f"{BASE}/channels/CH1/messages"
    assert fake.request_body()["content"] == "hello world"


def test_send_message_too_long_exits(monkeypatch):
    # No urlopen patch: must exit before any network call.
    with pytest.raises(SystemExit):
        run_cli(
            mod,
            ["send-message", "CH1", "x" * (mod.MAX_MESSAGE_LEN + 1)],
            monkeypatch,
        )


def test_read_messages(monkeypatch, capsys):
    msgs = [
        {"id": "m2", "author": {"username": "bob"}, "content": "second"},
        {"id": "m1", "author": {"username": "alice"}, "content": "first"},
    ]
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router({("GET", f"{BASE}/channels/CH1/messages"): msgs}),
    )
    run_cli(mod, ["read-messages", "CH1", "--limit", "5"], monkeypatch)
    out = capsys.readouterr().out
    # reversed -> chronological order
    assert out.index("alice: first") < out.index("bob: second")
    assert fake.last_request.full_url.startswith(f"{BASE}/channels/CH1/messages?")


def test_reply(monkeypatch, capsys):
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router({("POST", f"{BASE}/channels/CH1/messages"): {"id": "R1"}}),
    )
    run_cli(mod, ["reply", "CH1", "MSG1", "a reply"], monkeypatch)
    assert "Replied with message R1" in capsys.readouterr().out
    body = fake.request_body()
    assert body["content"] == "a reply"
    assert body["message_reference"] == {"message_id": "MSG1"}


def test_edit_message(monkeypatch, capsys):
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router(
            {("PATCH", f"{BASE}/channels/CH1/messages/MSG1"): FakeResponse(None, 204)}
        ),
    )
    run_cli(mod, ["edit-message", "CH1", "MSG1", "edited"], monkeypatch)
    assert "Edited message MSG1" in capsys.readouterr().out
    req = fake.last_request
    assert req.method == "PATCH"
    assert req.full_url == f"{BASE}/channels/CH1/messages/MSG1"
    assert fake.request_body()["content"] == "edited"


def test_delete_message(monkeypatch, capsys):
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router(
            {("DELETE", f"{BASE}/channels/CH1/messages/MSG1"): FakeResponse(None, 204)}
        ),
    )
    run_cli(mod, ["delete-message", "CH1", "MSG1"], monkeypatch)
    assert "Deleted message MSG1" in capsys.readouterr().out
    req = fake.last_request
    assert req.method == "DELETE"
    assert req.full_url == f"{BASE}/channels/CH1/messages/MSG1"


def test_add_reaction(monkeypatch, capsys):
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router(
            {
                (
                    "PUT",
                    f"{BASE}/channels/CH1/messages/MSG1/reactions/%F0%9F%91%8D/@me",
                ): FakeResponse(None, 204)
            }
        ),
    )
    run_cli(mod, ["add-reaction", "CH1", "MSG1", "\U0001f44d"], monkeypatch)
    assert "Reacted with" in capsys.readouterr().out
    req = fake.last_request
    assert req.method == "PUT"
    assert req.full_url.endswith("/reactions/%F0%9F%91%8D/@me")


def test_create_thread(monkeypatch, capsys):
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router(
            {
                ("POST", f"{BASE}/channels/CH1/messages/MSG1/threads"): {
                    "id": "T1",
                    "name": "my thread",
                }
            }
        ),
    )
    run_cli(mod, ["create-thread", "CH1", "MSG1", "my thread"], monkeypatch)
    assert "Created thread 'my thread' (id: T1)" in capsys.readouterr().out
    assert fake.request_body()["name"] == "my thread"


def test_list_threads(monkeypatch, capsys):
    routes = {
        ("GET", f"{BASE}/channels/CH1"): {"id": "CH1", "guild_id": "G1"},
        ("GET", f"{BASE}/guilds/G1/threads/active"): {
            "threads": [
                {"id": "T1", "name": "alpha", "parent_id": "CH1"},
                {"id": "T2", "name": "other", "parent_id": "OTHER"},
            ]
        },
    }
    patch_urlopen(monkeypatch, mod, _router(routes))
    run_cli(mod, ["list-threads", "CH1"], monkeypatch)
    out = capsys.readouterr().out
    assert "- alpha  (id: T1)" in out
    assert "other" not in out


def test_list_threads_unsupported_channel(monkeypatch):
    patch_urlopen(
        monkeypatch,
        mod,
        _router({("GET", f"{BASE}/channels/CH1"): {"id": "CH1"}}),
    )
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-threads", "CH1"], monkeypatch)


def test_search_messages(monkeypatch, capsys):
    msgs = [
        {"id": "m1", "author": {"username": "alice"}, "content": "hello world"},
        {"id": "m2", "author": {"username": "bob"}, "content": "nothing here"},
    ]
    patch_urlopen(
        monkeypatch,
        mod,
        _router({("GET", f"{BASE}/channels/CH1/messages"): msgs}),
    )
    run_cli(mod, ["search-messages", "CH1", "world"], monkeypatch)
    out = capsys.readouterr().out
    assert "alice: hello world" in out
    assert "bob" not in out


def test_search_messages_no_match(monkeypatch, capsys):
    msgs = [{"id": "m1", "author": {"username": "alice"}, "content": "hello"}]
    patch_urlopen(
        monkeypatch,
        mod,
        _router({("GET", f"{BASE}/channels/CH1/messages"): msgs}),
    )
    run_cli(mod, ["search-messages", "CH1", "absent"], monkeypatch)
    assert "No messages matching 'absent'" in capsys.readouterr().out


def test_send_embed(monkeypatch, capsys):
    fake = patch_urlopen(
        monkeypatch,
        mod,
        _router({("POST", f"{BASE}/channels/CH1/messages"): {"id": "E1"}}),
    )
    run_cli(
        mod,
        ["send-embed", "CH1", "Title", "Desc", "--color", "255", "--url", "http://x"],
        monkeypatch,
    )
    assert "Sent embed message E1" in capsys.readouterr().out
    embed = fake.request_body()["embeds"][0]
    assert embed["title"] == "Title"
    assert embed["description"] == "Desc"
    assert embed["color"] == 255
    assert embed["url"] == "http://x"


def test_http_error_exits(monkeypatch):
    patch_urlopen(
        monkeypatch,
        mod,
        _router(
            {("GET", f"{BASE}/users/@me/guilds"): http_error(401, {"message": "no"})}
        ),
    )
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-guilds"], monkeypatch)
