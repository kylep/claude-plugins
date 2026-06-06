import base64
import json
import subprocess

import pytest

from conftest import load_script, run_cli

mod = load_script("bitwarden")
pytestmark = pytest.mark.integration

SESSION = "test-session"


class FakeCompleted:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class FakeRun:
    """Callable subprocess.run replacement.

    Mimics subprocess.run's signature (args first, then keyword-only options
    the script passes: capture_output, text, env, timeout). Records every call
    and returns canned CompletedProcess-like results, either from a list
    consumed in order or from a callable taking the argv list.
    """

    def __init__(self, results):
        self._results = results
        self.calls = []

    def __call__(self, args, capture_output=False, text=False, env=None,
                 timeout=None, **kwargs):
        self.calls.append({
            "args": args,
            "capture_output": capture_output,
            "text": text,
            "env": env,
            "timeout": timeout,
        })
        if callable(self._results):
            result = self._results(args)
        else:
            result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    @property
    def last_args(self):
        return self.calls[-1]["args"]

    def args_at(self, index):
        return self.calls[index]["args"]


def patch_run(monkeypatch, results):
    fake = FakeRun(results)
    monkeypatch.setattr(mod.subprocess, "run", fake)
    return fake


def with_session(monkeypatch):
    monkeypatch.setenv("BW_SESSION", SESSION)


# ---------------------------------------------------------------------------
# Common assertions about how `bw` is invoked
# ---------------------------------------------------------------------------


def assert_bw_invocation(call_args, expected_subargs):
    """The script builds: ['bw', *args, '--session', SESSION]."""
    assert call_args == ["bw", *expected_subargs, "--session", SESSION]


def assert_session_passed(call):
    assert call["env"]["BW_SESSION"] == SESSION
    assert call["timeout"] == 30
    assert call["capture_output"] is True
    assert call["text"] is True


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status(monkeypatch, capsys):
    with_session(monkeypatch)
    fake = patch_run(monkeypatch, [FakeCompleted(stdout='{"status":"unlocked"}\n')])
    run_cli(mod, ["status"], monkeypatch)

    out = capsys.readouterr().out
    assert '{"status":"unlocked"}' in out
    assert_bw_invocation(fake.last_args, ["status"])
    assert_session_passed(fake.calls[-1])


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


def test_sync(monkeypatch, capsys):
    with_session(monkeypatch)
    fake = patch_run(monkeypatch, [FakeCompleted(stdout="Syncing complete.")])
    run_cli(mod, ["sync"], monkeypatch)

    out = capsys.readouterr().out
    assert "Vault synced." in out
    assert_bw_invocation(fake.last_args, ["sync"])
    assert_session_passed(fake.calls[-1])


# ---------------------------------------------------------------------------
# list-items
# ---------------------------------------------------------------------------


def test_list_items_renders(monkeypatch, capsys):
    with_session(monkeypatch)
    items = [
        {"name": "GitHub", "id": "i1", "type": 1, "login": {"username": "alice"}},
        {"name": "Note", "id": "i2", "type": 2},
    ]
    fake = patch_run(monkeypatch, [FakeCompleted(stdout=json.dumps(items))])
    run_cli(mod, ["list-items"], monkeypatch)

    out = capsys.readouterr().out
    assert "Found 2 item(s):" in out
    assert "**GitHub** (login) [id: i1]" in out
    assert "Username: alice" in out
    assert "**Note** (secure_note) [id: i2]" in out
    assert_bw_invocation(fake.last_args, ["list", "items"])


def test_list_items_empty(monkeypatch, capsys):
    with_session(monkeypatch)
    patch_run(monkeypatch, [FakeCompleted(stdout="[]")])
    run_cli(mod, ["list-items"], monkeypatch)
    assert "No items found." in capsys.readouterr().out


def test_list_items_with_all_filters(monkeypatch, capsys):
    with_session(monkeypatch)
    fake = patch_run(monkeypatch, [FakeCompleted(stdout="[]")])
    run_cli(
        mod,
        [
            "list-items",
            "--search", "git",
            "--folder-id", "f1",
            "--collection-id", "c1",
        ],
        monkeypatch,
    )
    assert_bw_invocation(
        fake.last_args,
        ["list", "items", "--search", "git", "--folderid", "f1",
         "--collectionid", "c1"],
    )


# ---------------------------------------------------------------------------
# get-item
# ---------------------------------------------------------------------------


def test_get_item_includes_password(monkeypatch, capsys):
    with_session(monkeypatch)
    item = {
        "name": "GitHub",
        "id": "i1",
        "type": 1,
        "login": {"username": "alice", "password": "s3cret"},
    }
    fake = patch_run(monkeypatch, [FakeCompleted(stdout=json.dumps(item))])
    run_cli(mod, ["get-item", "GitHub"], monkeypatch)

    out = capsys.readouterr().out
    assert "Username: alice" in out
    assert "Password: s3cret" in out
    assert_bw_invocation(fake.last_args, ["get", "item", "GitHub"])


# ---------------------------------------------------------------------------
# create-item
# ---------------------------------------------------------------------------


def test_create_item(monkeypatch, capsys):
    with_session(monkeypatch)
    item_template = {"name": "", "type": 0, "notes": None, "folderId": None}
    login_template = {"username": None, "password": None, "uris": []}
    created = {
        "name": "NewAcct",
        "id": "new-1",
        "type": 1,
        "login": {"username": "bob"},
    }
    results = [
        FakeCompleted(stdout=json.dumps(item_template)),   # get template item
        FakeCompleted(stdout=json.dumps(login_template)),  # get template item.login
        FakeCompleted(stdout=json.dumps(created)),         # create item <b64>
    ]
    fake = patch_run(monkeypatch, results)
    run_cli(
        mod,
        [
            "create-item", "NewAcct",
            "--username", "bob",
            "--password", "pw",
            "--uri", "https://x.test",
            "--notes", "n",
            "--folder-id", "f1",
        ],
        monkeypatch,
    )

    out = capsys.readouterr().out
    assert "Created item:" in out
    assert "**NewAcct** (login) [id: new-1]" in out

    # Verify the three bw invocations.
    assert_bw_invocation(fake.args_at(0), ["get", "template", "item"])
    assert_bw_invocation(fake.args_at(1), ["get", "template", "item.login"])

    create_args = fake.args_at(2)
    assert create_args[:3] == ["bw", "create", "item"]
    encoded = create_args[3]
    payload = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert payload["name"] == "NewAcct"
    assert payload["type"] == 1
    assert payload["notes"] == "n"
    assert payload["folderId"] == "f1"
    assert payload["login"]["username"] == "bob"
    assert payload["login"]["password"] == "pw"
    assert payload["login"]["uris"] == [{"match": None, "uri": "https://x.test"}]


def test_create_item_without_uri_yields_empty_uris(monkeypatch, capsys):
    with_session(monkeypatch)
    results = [
        FakeCompleted(stdout="{}"),
        FakeCompleted(stdout="{}"),
        FakeCompleted(stdout=json.dumps({"name": "A", "id": "1", "type": 1})),
    ]
    fake = patch_run(monkeypatch, results)
    run_cli(mod, ["create-item", "A"], monkeypatch)

    payload = json.loads(base64.b64decode(fake.args_at(2)[3]).decode("utf-8"))
    assert payload["login"]["uris"] == []


# ---------------------------------------------------------------------------
# edit-item
# ---------------------------------------------------------------------------


def test_edit_item_login_fields(monkeypatch, capsys):
    with_session(monkeypatch)
    existing = {
        "name": "Old",
        "id": "e1",
        "type": 1,
        "login": {"username": "old", "password": "old"},
    }
    updated = {"name": "New", "id": "e1", "type": 1, "login": {"username": "new"}}
    fake = patch_run(monkeypatch, [
        FakeCompleted(stdout=json.dumps(existing)),  # get item
        FakeCompleted(stdout=json.dumps(updated)),   # edit item
    ])
    run_cli(
        mod,
        [
            "edit-item", "e1",
            "--name", "New",
            "--username", "new",
            "--password", "newpw",
            "--uri", "https://new.test",
            "--notes", "newnotes",
        ],
        monkeypatch,
    )

    out = capsys.readouterr().out
    assert "Updated item:" in out
    assert "**New** (login) [id: e1]" in out

    assert_bw_invocation(fake.args_at(0), ["get", "item", "e1"])

    edit_args = fake.args_at(1)
    assert edit_args[:4] == ["bw", "edit", "item", "e1"]
    payload = json.loads(base64.b64decode(edit_args[4]).decode("utf-8"))
    assert payload["name"] == "New"
    assert payload["notes"] == "newnotes"
    assert payload["login"]["username"] == "new"
    assert payload["login"]["password"] == "newpw"
    assert payload["login"]["uris"] == [{"match": None, "uri": "https://new.test"}]


def test_edit_item_rejects_login_fields_on_non_login(monkeypatch):
    with_session(monkeypatch)
    existing = {"name": "Note", "id": "n1", "type": 2}
    patch_run(monkeypatch, [FakeCompleted(stdout=json.dumps(existing))])
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["edit-item", "n1", "--username", "x"], monkeypatch)
    assert "Cannot set login fields" in str(exc.value)


# ---------------------------------------------------------------------------
# delete-item
# ---------------------------------------------------------------------------


def test_delete_item(monkeypatch, capsys):
    with_session(monkeypatch)
    fake = patch_run(monkeypatch, [FakeCompleted(stdout="")])
    run_cli(mod, ["delete-item", "d1"], monkeypatch)

    out = capsys.readouterr().out
    assert "Deleted item d1" in out
    assert_bw_invocation(fake.last_args, ["delete", "item", "d1"])


# ---------------------------------------------------------------------------
# generate-password
# ---------------------------------------------------------------------------


def test_generate_password_defaults(monkeypatch, capsys):
    with_session(monkeypatch)
    fake = patch_run(monkeypatch, [FakeCompleted(stdout="Abc123!@#")])
    run_cli(mod, ["generate-password"], monkeypatch)

    out = capsys.readouterr().out
    assert "Abc123!@#" in out
    assert_bw_invocation(
        fake.last_args,
        ["generate", "--length", "20", "--uppercase", "--lowercase",
         "--number", "--special"],
    )


def test_generate_password_with_disables(monkeypatch, capsys):
    with_session(monkeypatch)
    fake = patch_run(monkeypatch, [FakeCompleted(stdout="abcdefgh")])
    run_cli(
        mod,
        [
            "generate-password",
            "--length", "8",
            "--no-uppercase",
            "--no-numbers",
            "--no-special",
        ],
        monkeypatch,
    )
    assert_bw_invocation(
        fake.last_args,
        ["generate", "--length", "8", "--lowercase"],
    )


# ---------------------------------------------------------------------------
# list-folders
# ---------------------------------------------------------------------------


def test_list_folders_renders(monkeypatch, capsys):
    with_session(monkeypatch)
    folders = [{"name": "Work", "id": "f1"}, {"name": "Personal", "id": "f2"}]
    fake = patch_run(monkeypatch, [FakeCompleted(stdout=json.dumps(folders))])
    run_cli(mod, ["list-folders"], monkeypatch)

    out = capsys.readouterr().out
    assert "- **Work** [f1]" in out
    assert "- **Personal** [f2]" in out
    assert_bw_invocation(fake.last_args, ["list", "folders"])


def test_list_folders_empty(monkeypatch, capsys):
    with_session(monkeypatch)
    patch_run(monkeypatch, [FakeCompleted(stdout="[]")])
    run_cli(mod, ["list-folders"], monkeypatch)
    assert "No folders." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_nonzero_returncode_exits_with_stderr(monkeypatch):
    with_session(monkeypatch)
    patch_run(monkeypatch, [
        FakeCompleted(stdout="", stderr="vault is locked", returncode=1)
    ])
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["status"], monkeypatch)
    assert "bw error: vault is locked" in str(exc.value)


def test_nonzero_returncode_falls_back_to_stdout(monkeypatch):
    with_session(monkeypatch)
    patch_run(monkeypatch, [
        FakeCompleted(stdout="some stdout", stderr="", returncode=2)
    ])
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["status"], monkeypatch)
    assert "bw error: some stdout" in str(exc.value)


def test_timeout_exits(monkeypatch):
    with_session(monkeypatch)
    patch_run(monkeypatch, lambda args: (_ for _ in ()).throw(
        subprocess.TimeoutExpired(cmd=args, timeout=30)
    ))
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["status"], monkeypatch)
    assert "timed out" in str(exc.value)


def test_bw_not_found_exits(monkeypatch):
    with_session(monkeypatch)
    patch_run(monkeypatch, lambda args: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["status"], monkeypatch)
    assert "not found on PATH" in str(exc.value)


def test_missing_session_exits_before_subprocess(monkeypatch):
    monkeypatch.delenv("BW_SESSION", raising=False)
    # Patch run to blow up if it is ever reached; the script should exit first.
    patch_run(monkeypatch, lambda args: (_ for _ in ()).throw(
        AssertionError("subprocess.run should not be called without BW_SESSION")
    ))
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["status"], monkeypatch)
    assert "BW_SESSION" in str(exc.value)
