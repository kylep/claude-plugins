"""Integration tests for desktop.py with a fully mocked subprocess layer.

Every test that reaches a command path patches ``mod.subprocess.run`` first, so
no real ``screencapture`` / ``cliclick`` / ``osascript`` ever fires and no real
desktop action can occur. The fake records the exact argv it was handed and, for
screenshot captures, writes canned PNG bytes to the path the script chose so the
read-back / base64 path works without a real screen grab.
"""

import base64
import subprocess

import pytest

from conftest import load_script, run_cli

mod = load_script("desktop")
pytestmark = pytest.mark.integration

PNG_BYTES = b"\x89PNG\r\n\x1a\nFAKEDATA"


class FakeCompleted:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRun:
    """Records every subprocess.run invocation and returns a canned result.

    For a ``screencapture -x <path>`` call it writes PNG_BYTES to <path> so the
    script's read-back of the screenshot file succeeds without a real capture.
    """

    def __init__(self, result=None, exc=None, png_bytes=PNG_BYTES):
        self._result = result or FakeCompleted()
        self._exc = exc
        self._png = png_bytes
        self.calls = []

    def __call__(self, cmd, capture_output=None, text=None, timeout=None, **kwargs):
        self.calls.append(
            {"cmd": tuple(cmd), "timeout": timeout,
             "capture_output": capture_output, "text": text}
        )
        if self._exc is not None:
            raise self._exc
        if cmd and cmd[0] == "screencapture" and self._png is not None:
            # cmd is ("screencapture", "-x", path)
            with open(cmd[-1], "wb") as fh:
                fh.write(self._png)
        return self._result

    @property
    def last_cmd(self):
        return self.calls[-1]["cmd"]


def patch_run(monkeypatch, **kwargs):
    fake = FakeRun(**kwargs)
    monkeypatch.setattr(mod.subprocess, "run", fake)
    return fake


@pytest.fixture(autouse=True)
def force_macos(monkeypatch):
    # All handlers call require_macos(); pin platform so tests run anywhere.
    monkeypatch.setattr(mod.sys, "platform", "darwin")


# ---------------------------------------------------------------------------
# take
# ---------------------------------------------------------------------------


def test_take_to_output_path_prints_path(monkeypatch, capsys, tmp_path):
    out_path = tmp_path / "shot.png"
    fake = patch_run(monkeypatch)
    run_cli(mod, ["take", "--output", str(out_path)], monkeypatch)

    assert fake.last_cmd == ("screencapture", "-x", str(out_path))
    assert fake.calls[0]["timeout"] == 30
    assert capsys.readouterr().out.strip() == str(out_path)
    # File left in place (not base64); our fake wrote canned bytes there.
    assert out_path.read_bytes() == PNG_BYTES


def test_take_default_temp_prints_temp_path(monkeypatch, capsys):
    fake = patch_run(monkeypatch)
    run_cli(mod, ["take"], monkeypatch)

    printed = capsys.readouterr().out.strip()
    assert fake.last_cmd[:2] == ("screencapture", "-x")
    # The path it captured to is the path it printed.
    assert fake.last_cmd[-1] == printed
    assert printed.endswith(".png")
    assert "screenshot-" in printed


def test_take_base64_encodes_file_contents(monkeypatch, capsys):
    fake = patch_run(monkeypatch)
    run_cli(mod, ["take", "--base64"], monkeypatch)

    out = capsys.readouterr().out.strip()
    assert out == base64.b64encode(PNG_BYTES).decode("ascii")
    assert fake.last_cmd[:2] == ("screencapture", "-x")


def test_take_base64_deletes_temp_file(monkeypatch, capsys):
    captured_path = {}

    def grabber(cmd, **kwargs):
        captured_path["p"] = cmd[-1]
        with open(cmd[-1], "wb") as fh:
            fh.write(PNG_BYTES)
        return FakeCompleted()

    monkeypatch.setattr(mod.subprocess, "run", grabber)
    run_cli(mod, ["take", "--base64"], monkeypatch)

    import os
    assert not os.path.exists(captured_path["p"]), "temp file should be cleaned up"


def test_take_output_with_base64_does_not_delete(monkeypatch, capsys, tmp_path):
    out_path = tmp_path / "keep.png"
    patch_run(monkeypatch)
    run_cli(mod, ["take", "--output", str(out_path), "--base64"], monkeypatch)

    out = capsys.readouterr().out.strip()
    assert out == base64.b64encode(PNG_BYTES).decode("ascii")
    assert out_path.exists()  # explicit output path is never deleted


# ---------------------------------------------------------------------------
# click / double-click / type
# ---------------------------------------------------------------------------


def test_click_runs_cliclick(monkeypatch, capsys):
    fake = patch_run(monkeypatch)
    run_cli(mod, ["click", "10", "20"], monkeypatch)

    assert fake.last_cmd == ("cliclick", "c:10,20")
    assert "Clicked at (10, 20)" in capsys.readouterr().out


def test_double_click_runs_cliclick(monkeypatch, capsys):
    fake = patch_run(monkeypatch)
    run_cli(mod, ["double-click", "3", "4"], monkeypatch)

    assert fake.last_cmd == ("cliclick", "dc:3,4")
    assert "Double-clicked at (3, 4)" in capsys.readouterr().out


def test_type_runs_cliclick(monkeypatch, capsys):
    fake = patch_run(monkeypatch)
    run_cli(mod, ["type", "hi there"], monkeypatch)

    assert fake.last_cmd == ("cliclick", "t:hi there")
    assert "Typed: hi there" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# error paths
# ---------------------------------------------------------------------------


def test_nonzero_returncode_exits_with_stderr(monkeypatch):
    patch_run(monkeypatch, result=FakeCompleted(returncode=1, stderr="boom"))
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["click", "1", "2"], monkeypatch)
    assert "cliclick failed: boom" in str(exc.value)


def test_nonzero_returncode_empty_stderr(monkeypatch):
    patch_run(monkeypatch, result=FakeCompleted(returncode=2, stderr="  "))
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["click", "1", "2"], monkeypatch)
    assert "(no stderr)" in str(exc.value)


def test_timeout_exits(monkeypatch):
    patch_run(monkeypatch, exc=subprocess.TimeoutExpired(cmd="cliclick", timeout=30))
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["type", "x"], monkeypatch)
    assert "timed out after 30s" in str(exc.value)


def test_cliclick_not_found_gives_install_hint(monkeypatch):
    patch_run(monkeypatch, exc=FileNotFoundError())
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["click", "1", "2"], monkeypatch)
    msg = str(exc.value)
    assert "cliclick" in msg and "brew install cliclick" in msg


def test_screencapture_not_found_generic_message(monkeypatch):
    patch_run(monkeypatch, exc=FileNotFoundError())
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["take", "--output", "/tmp/x.png"], monkeypatch)
    assert "`screencapture` not found on PATH." in str(exc.value)


def test_non_darwin_exits_before_subprocess(monkeypatch):
    # Override the autouse darwin pin; ensure no subprocess.run is reachable.
    monkeypatch.setattr(mod.sys, "platform", "linux")

    def explode(*a, **k):
        raise AssertionError("subprocess.run must not be called off darwin")

    monkeypatch.setattr(mod.subprocess, "run", explode)
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["click", "1", "2"], monkeypatch)
    assert "macOS-only" in str(exc.value)
