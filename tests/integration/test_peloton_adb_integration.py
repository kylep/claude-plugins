"""Integration tests for peloton_adb.py with a fully mocked adb.

Every test patches ``mod.subprocess.run`` so no real adb binary is invoked and
no device is touched. The fake records each argv and answers from a table keyed
on the adb sub-command, so each CLI subcommand can be checked end to end: the
exact adb calls it makes, in order, and what it prints.
"""

import subprocess

import pytest

from conftest import load_script, run_cli

mod = load_script("peloton_adb")
pytestmark = pytest.mark.integration

SERIAL = "10.0.0.5:41234"
GATE = "com.onepeloton.systempluginui"

DEVICES_ONE = f"List of devices attached\n{SERIAL}\tdevice product:RB1VQ model:PLTN_RB1VQ\n"


class FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeAdb:
    """Answers adb invocations from a responder(argv) -> str|FakeCompleted."""

    def __init__(self, responder=None):
        self.calls: list[tuple[str, ...]] = []
        self._responder = responder or (lambda argv: "")

    def __call__(self, cmd, capture_output=None, text=None, timeout=None, **kw):
        argv = tuple(cmd)
        self.calls.append(argv)
        out = self._responder(argv)
        if isinstance(out, BaseException):
            raise out
        if isinstance(out, FakeCompleted):
            return out
        return FakeCompleted(stdout=out)

    def shells(self):
        """Return the `adb shell ...` payloads that were run, as strings."""
        res = []
        for c in self.calls:
            if "shell" in c:
                res.append(" ".join(c[c.index("shell") + 1:]))
        return res


def _tail(argv):
    """argv after the `adb [-s SERIAL]` prefix."""
    a = list(argv[1:])
    if a[:1] == ["-s"]:
        a = a[2:]
    return a


@pytest.fixture
def fake(monkeypatch):
    """Install a FakeAdb whose responder can be set per-test via fake.respond."""
    holder = {}

    def responder(argv):
        fn = holder.get("fn")
        return fn(argv) if fn else ""

    f = FakeAdb(responder)
    f.respond = lambda fn: holder.__setitem__("fn", fn)
    monkeypatch.setattr(mod.subprocess, "run", f)
    monkeypatch.delenv("PELOTON_ADB_SERIAL", raising=False)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return f


def devices_then(fn):
    """Responder that answers `adb devices -l` with one device, else defers."""

    def inner(argv):
        t = _tail(argv)
        if t[:1] == ["devices"]:
            return DEVICES_ONE
        return fn(t)

    return inner


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------


def test_connect_without_pair_only_connects(fake, monkeypatch, capsys):
    fake.respond(lambda argv: "connected to 10.0.0.5:41234" if "connect" in argv else "")
    run_cli(mod, ["connect", "10.0.0.5:41234"], monkeypatch)
    assert fake.calls == [("adb", "connect", "10.0.0.5:41234")]
    assert "connected to" in capsys.readouterr().out


def test_connect_with_pair_pairs_first(fake, monkeypatch, capsys):
    fake.respond(lambda argv: "Successfully paired" if "pair" in argv else "connected to 10.0.0.5:41234")
    run_cli(mod, ["connect", "10.0.0.5:41234", "--pair", "10.0.0.5:45945", "--code", "123456"], monkeypatch)
    assert fake.calls == [
        ("adb", "pair", "10.0.0.5:45945", "123456"),
        ("adb", "connect", "10.0.0.5:41234"),
    ]


def test_connect_pair_requires_code(fake, monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(mod, ["connect", "10.0.0.5:41234", "--pair", "10.0.0.5:45945"], monkeypatch)
    assert fake.calls == []


def test_connect_failure_exits_nonzero_with_adb_text(fake, monkeypatch):
    fake.respond(lambda argv: "failed to connect to '10.0.0.5:41234': Connection refused")
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["connect", "10.0.0.5:41234"], monkeypatch)
    assert "Connection refused" in str(exc.value)


def test_connect_warns_when_inside_tmux_on_macos(fake, monkeypatch, capsys):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1/default,1,0")
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    fake.respond(lambda argv: "connected to 10.0.0.5:41234")
    run_cli(mod, ["connect", "10.0.0.5:41234"], monkeypatch)
    assert "tmux" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# stable-port
# ---------------------------------------------------------------------------


def test_stable_port_switches_to_tcpip_then_reconnects(fake, monkeypatch):
    fake.respond(devices_then(lambda t: "restarting in TCP mode port: 5555" if t[:1] == ["tcpip"] else "connected to 10.0.0.5:5555"))
    run_cli(mod, ["stable-port"], monkeypatch)
    assert ("adb", "-s", SERIAL, "tcpip", "5555") in fake.calls
    assert fake.calls[-1] == ("adb", "connect", "10.0.0.5:5555")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def _status_responder(t):
    s = " ".join(t)
    if t[:1] == ["shell"]:
        if "getprop ro.build.version.release" in s:
            return "11\n"
        if "getprop ro.build.display.id" in s:
            return "RQ.000000.A\n"
        if "getprop ro.product.model" in s:
            return "PLTN_RB1VQ\n"
        if "pm list packages -d" in s:
            return ""
        if "pm list packages -3" in s:
            return "package:app.lawnchair\npackage:com.netflix.mediaclient\n"
        if "pidof" in s:
            return "8915\n"
        if "resolve-activity" in s:
            return "  packageName=app.lawnchair\n  name=app.lawnchair.LawnchairLauncher\n"
        if "adb_wifi_enabled" in s:
            return "1\n"
    return ""


def test_status_reports_gate_launcher_and_packages(fake, monkeypatch, capsys):
    fake.respond(devices_then(_status_responder))
    run_cli(mod, ["status"], monkeypatch)
    out = capsys.readouterr().out
    assert "Android 11" in out
    assert "PLTN_RB1VQ" in out
    assert "enabled (running, pid 8915)" in out
    assert "app.lawnchair" in out
    assert "com.netflix.mediaclient" in out
    # every adb call after `devices` targeted the resolved serial
    assert all(c[1:3] == ("-s", SERIAL) for c in fake.calls[1:])


# ---------------------------------------------------------------------------
# unblock / reblock
# ---------------------------------------------------------------------------


def test_unblock_disables_force_stops_and_verifies(fake, monkeypatch, capsys):
    def r(t):
        s = " ".join(t)
        if "pm disable-user" in s:
            return f"Package {GATE} new state: disabled-user\n"
        if "pm list packages -d" in s:
            return f"package:{GATE}\n"
        return ""

    fake.respond(devices_then(r))
    run_cli(mod, ["unblock"], monkeypatch)
    sh = fake.shells()
    assert sh[0] == f"pm disable-user --user 0 {GATE}"
    assert sh[1] == f"am force-stop {GATE}"
    assert any("pm list packages -d" in x for x in sh)
    assert "disabled" in capsys.readouterr().out


def test_unblock_exits_if_disable_did_not_stick(fake, monkeypatch):
    fake.respond(devices_then(lambda t: ""))  # pm list -d shows nothing disabled
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["unblock"], monkeypatch)
    assert "still enabled" in str(exc.value)


def test_reblock_enables_and_verifies(fake, monkeypatch, capsys):
    fake.respond(devices_then(lambda t: f"Package {GATE} new state: enabled\n" if "pm enable" in " ".join(t) else ""))
    run_cli(mod, ["reblock"], monkeypatch)
    assert fake.shells()[0] == f"pm enable --user 0 {GATE}"
    assert "enabled" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# install / launch / diagnose
# ---------------------------------------------------------------------------


def test_install_installs_each_apk_with_replace(fake, monkeypatch, tmp_path):
    a = tmp_path / "a.apk"
    b = tmp_path / "b.apk"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    fake.respond(devices_then(lambda t: "Success\n"))
    run_cli(mod, ["install", str(a), str(b)], monkeypatch)
    installs = [c for c in fake.calls if "install" in c]
    assert installs == [
        ("adb", "-s", SERIAL, "install", "-r", str(a)),
        ("adb", "-s", SERIAL, "install", "-r", str(b)),
    ]


def test_install_rejects_missing_file_before_touching_device(fake, monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        run_cli(mod, ["install", str(tmp_path / "nope.apk")], monkeypatch)
    assert not any("install" in c for c in fake.calls)


def test_launch_uses_monkey_launcher_intent(fake, monkeypatch):
    fake.respond(devices_then(lambda t: "Events injected: 1\n"))
    run_cli(mod, ["launch", "com.netflix.mediaclient"], monkeypatch)
    assert fake.shells()[-1] == "monkey -p com.netflix.mediaclient -c android.intent.category.LAUNCHER 1"


def test_diagnose_reports_membership_gate_kill(fake, monkeypatch, capsys):
    log = (
        "09-12 W/AuthValidator( 8915): No authenticated user found, sending user to login screen\n"
        "09-12 W/ActivityTaskManager(  616): Force removing ActivityRecord{x u0 com.netflix.mediaclient/.ui.launch.UIWebViewActivity}: app died, no saved state\n"
    )

    def r(t):
        s = " ".join(t)
        if "logcat -d" in s:
            return log
        if "pidof" in s:
            return ""
        return ""

    fake.respond(devices_then(r))
    run_cli(mod, ["diagnose", "com.netflix.mediaclient"], monkeypatch)
    sh = fake.shells()
    assert sh[0] == "logcat -c"
    assert sh[1].startswith("monkey -p com.netflix.mediaclient")
    out = capsys.readouterr().out
    assert "KILLED by membership gate" in out
    assert "unblock" in out  # tells the user the fix


def test_diagnose_reports_running(fake, monkeypatch, capsys):
    fake.respond(devices_then(lambda t: "14743\n" if "pidof" in " ".join(t) else ""))
    run_cli(mod, ["diagnose", "com.netflix.mediaclient", "--wait", "1"], monkeypatch)
    assert "RUNNING" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# error paths
# ---------------------------------------------------------------------------


def test_missing_adb_binary_is_a_clear_error(fake, monkeypatch):
    fake.respond(lambda argv: FileNotFoundError("adb"))
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["connect", "10.0.0.5:41234"], monkeypatch)
    assert "platform-tools" in str(exc.value)


def test_adb_timeout_is_a_clear_error(fake, monkeypatch):
    fake.respond(lambda argv: subprocess.TimeoutExpired(cmd="adb", timeout=1))
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["connect", "10.0.0.5:41234"], monkeypatch)
    assert "timed out" in str(exc.value)


def test_explicit_serial_flag_overrides_discovery(fake, monkeypatch):
    fake.respond(lambda argv: "")
    with pytest.raises(SystemExit):  # unblock verification fails on empty output, fine
        run_cli(mod, ["-s", "10.0.0.9:1", "unblock"], monkeypatch)
    assert not any("devices" in c for c in fake.calls)
    assert fake.calls[0][:3] == ("adb", "-s", "10.0.0.9:1")
