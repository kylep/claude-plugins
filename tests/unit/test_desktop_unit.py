"""Unit tests for the macos-desktop-control desktop.py script.

These tests never touch subprocess. They patch the module-level ``run`` helper
(which is the only thing that would shell out) so they can assert on the exact
argv each subcommand constructs, plus exercise the pure platform guard.
"""

import argparse

import pytest

from conftest import load_script, run_cli

mod = load_script("desktop")
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# require_macos: pure platform guard
# ---------------------------------------------------------------------------


def test_require_macos_passes_on_darwin(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    # Should not raise / exit.
    assert mod.require_macos() is None


def test_require_macos_exits_off_darwin(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "linux")
    with pytest.raises(SystemExit) as exc:
        mod.require_macos()
    assert "macOS-only" in str(exc.value)


# ---------------------------------------------------------------------------
# argv construction for the click/type family
#
# We patch the module's ``run`` so nothing shells out, and capture the exact
# tuple of args each subcommand builds.
# ---------------------------------------------------------------------------


@pytest.fixture
def captured_runs(monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "run", lambda *cmd: calls.append(cmd))
    # require_macos is a no-op so coordinate handlers never gate on platform.
    monkeypatch.setattr(mod, "require_macos", lambda: None)
    return calls


def _ns(**kw):
    return argparse.Namespace(**kw)


def test_cmd_click_builds_cliclick_c(captured_runs, capsys):
    mod.cmd_click(_ns(x=12, y=34))
    assert captured_runs == [("cliclick", "c:12,34")]
    assert "Clicked at (12, 34)" in capsys.readouterr().out


def test_cmd_double_click_builds_cliclick_dc(captured_runs, capsys):
    mod.cmd_double_click(_ns(x=5, y=6))
    assert captured_runs == [("cliclick", "dc:5,6")]
    assert "Double-clicked at (5, 6)" in capsys.readouterr().out


def test_cmd_type_builds_cliclick_t(captured_runs, capsys):
    mod.cmd_type(_ns(text="hello world"))
    assert captured_runs == [("cliclick", "t:hello world")]
    assert "Typed: hello world" in capsys.readouterr().out


def test_cmd_click_negative_coordinates(captured_runs):
    mod.cmd_click(_ns(x=-1, y=-2))
    assert captured_runs == [("cliclick", "c:-1,-2")]


# ---------------------------------------------------------------------------
# argparse wiring: the CLI maps subcommands to the right handler and coerces
# coordinates to ints. We patch the handlers so nothing runs.
# ---------------------------------------------------------------------------


def test_main_routes_click_with_int_coords(monkeypatch):
    seen = {}
    monkeypatch.setattr(mod, "cmd_click", lambda a: seen.update(x=a.x, y=a.y))
    run_cli(mod, ["click", "100", "200"], monkeypatch)
    assert seen == {"x": 100, "y": 200}
    assert isinstance(seen["x"], int) and isinstance(seen["y"], int)


def test_main_routes_double_click(monkeypatch):
    seen = {}
    monkeypatch.setattr(mod, "cmd_double_click", lambda a: seen.update(x=a.x, y=a.y))
    run_cli(mod, ["double-click", "1", "2"], monkeypatch)
    assert seen == {"x": 1, "y": 2}


def test_main_routes_type(monkeypatch):
    seen = {}
    monkeypatch.setattr(mod, "cmd_type", lambda a: seen.update(text=a.text))
    run_cli(mod, ["type", "abc"], monkeypatch)
    assert seen == {"text": "abc"}


def test_main_routes_take(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mod, "cmd_take", lambda a: seen.update(output=a.output, base64=a.base64)
    )
    run_cli(mod, ["take"], monkeypatch)
    assert seen == {"output": None, "base64": False}


def test_main_take_parses_flags(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mod, "cmd_take", lambda a: seen.update(output=a.output, base64=a.base64)
    )
    run_cli(mod, ["take", "--output", "/tmp/x.png", "--base64"], monkeypatch)
    assert seen == {"output": "/tmp/x.png", "base64": True}


def test_main_requires_subcommand(monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(mod, [], monkeypatch)


def test_main_rejects_non_int_coords(monkeypatch):
    monkeypatch.setattr(mod, "cmd_click", lambda a: None)
    with pytest.raises(SystemExit):
        run_cli(mod, ["click", "notanint", "5"], monkeypatch)
