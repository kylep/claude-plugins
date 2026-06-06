import base64
import json

import pytest

from conftest import load_script

mod = load_script("bitwarden")
pytestmark = pytest.mark.unit


def test_type_names_map():
    assert mod.TYPE_NAMES == {
        1: "login",
        2: "secure_note",
        3: "card",
        4: "identity",
    }


def test_format_item_minimal_login():
    item = {"name": "GitHub", "id": "abc-123", "type": 1}
    out = mod.format_item(item)
    assert out == "**GitHub** (login) [id: abc-123]"


def test_format_item_unknown_type():
    item = {"name": "Mystery", "id": "x", "type": 99}
    out = mod.format_item(item)
    assert "(unknown)" in out


def test_format_item_missing_type_defaults_to_unknown():
    # No "type" key -> .get("type", 0) -> 0 -> not in TYPE_NAMES -> unknown
    item = {"name": "NoType", "id": "y"}
    out = mod.format_item(item)
    assert "(unknown)" in out


def test_format_item_includes_username_uris_notes_folder():
    item = {
        "name": "Acct",
        "id": "id1",
        "type": 1,
        "login": {
            "username": "alice",
            "password": "hunter2",
            "uris": [{"uri": "https://a.test"}, {"uri": "https://b.test"}],
        },
        "notes": "hello world",
        "folderId": "folder-9",
    }
    out = mod.format_item(item)
    assert "Username: alice" in out
    assert "URLs: https://a.test, https://b.test" in out
    assert "Notes: hello world" in out
    assert "Folder: folder-9" in out
    # password excluded by default
    assert "Password:" not in out
    assert "hunter2" not in out


def test_format_item_password_only_when_requested():
    item = {
        "name": "Acct",
        "id": "id1",
        "type": 1,
        "login": {"username": "alice", "password": "hunter2"},
    }
    without = mod.format_item(item, include_password=False)
    assert "Password:" not in without
    with_pw = mod.format_item(item, include_password=True)
    assert "Password: hunter2" in with_pw


def test_format_item_password_skipped_if_empty_even_when_requested():
    item = {"name": "Acct", "id": "id1", "type": 1, "login": {"password": ""}}
    out = mod.format_item(item, include_password=True)
    assert "Password:" not in out


def test_format_item_uris_filters_blank_entries():
    item = {
        "name": "Acct",
        "id": "id1",
        "type": 1,
        "login": {"uris": [{"uri": "https://a.test"}, {"uri": ""}, {"match": None}]},
    }
    out = mod.format_item(item)
    assert "URLs: https://a.test" in out
    # blank/missing uris should not introduce a trailing comma
    assert "https://a.test," not in out


def test_format_item_no_uris_line_when_empty():
    item = {"name": "Acct", "id": "id1", "type": 1, "login": {"uris": []}}
    out = mod.format_item(item)
    assert "URLs:" not in out


def test_format_item_notes_truncated_to_200_chars():
    long = "z" * 500
    item = {"name": "Acct", "id": "id1", "type": 2, "notes": long}
    out = mod.format_item(item)
    notes_line = [l for l in out.splitlines() if "Notes:" in l][0]
    assert notes_line == "  Notes: " + "z" * 200


def test_format_item_handles_null_login():
    # bw returns "login": null for secure notes; script uses `or {}`
    item = {"name": "Note", "id": "n1", "type": 2, "login": None}
    out = mod.format_item(item)
    assert "**Note** (secure_note) [id: n1]" in out
    assert "Username:" not in out


def test_base64_roundtrip_of_template():
    # Mirrors the encoding the create/edit paths perform.
    template = {"name": "X", "type": 1, "login": {"username": "u"}}
    encoded = base64.b64encode(json.dumps(template).encode("utf-8")).decode("ascii")
    decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert decoded == template
