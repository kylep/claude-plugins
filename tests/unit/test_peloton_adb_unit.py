"""Unit tests for the sideloading-peloton-apps peloton_adb.py script.

Pure logic only: parsing adb output, classifying the membership-gate state,
resolving which device serial to talk to, and the diagnose verdict. Nothing
here shells out.
"""

import pytest

from conftest import load_script

mod = load_script("peloton_adb")
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# parse_devices: `adb devices -l` output -> list of (serial, state)
# ---------------------------------------------------------------------------

DEVICES_TWO = """List of devices attached
10.0.0.5:41234    device product:RB1VQ model:PLTN_RB1VQ device:RB1VQ transport_id:2
adb-XXXX._adb-tls-connect._tcp device product:RB1VQ model:PLTN_RB1VQ device:RB1VQ transport_id:1
"""


def test_parse_devices_skips_header_and_blank_lines():
    assert mod.parse_devices("List of devices attached\n\n") == []


def test_parse_devices_returns_serial_and_state():
    got = mod.parse_devices(DEVICES_TWO)
    assert got == [
        ("10.0.0.5:41234", "device"),
        ("adb-XXXX._adb-tls-connect._tcp", "device"),
    ]


def test_parse_devices_keeps_offline_state():
    out = "List of devices attached\n10.0.0.5:5555\toffline\n"
    assert mod.parse_devices(out) == [("10.0.0.5:5555", "offline")]


# ---------------------------------------------------------------------------
# resolve_serial: explicit > env > single attached device; else exit
# ---------------------------------------------------------------------------


def test_resolve_serial_prefers_explicit(monkeypatch):
    monkeypatch.setenv("PELOTON_ADB_SERIAL", "env:1")
    assert mod.resolve_serial("cli:1", lambda: []) == "cli:1"


def test_resolve_serial_uses_env_when_no_explicit(monkeypatch):
    monkeypatch.setenv("PELOTON_ADB_SERIAL", "env:1")
    assert mod.resolve_serial(None, lambda: []) == "env:1"


def test_resolve_serial_picks_only_online_device(monkeypatch):
    monkeypatch.delenv("PELOTON_ADB_SERIAL", raising=False)
    devs = [("a:1", "offline"), ("b:2", "device")]
    assert mod.resolve_serial(None, lambda: devs) == "b:2"


def test_resolve_serial_prefers_ip_port_over_mdns_alias(monkeypatch):
    # Wireless debugging lists the same bike twice; the ip:port form is the
    # one the user typed and the one that survives `adb tcpip`.
    monkeypatch.delenv("PELOTON_ADB_SERIAL", raising=False)
    devs = [("adb-XXXX._adb-tls-connect._tcp", "device"), ("10.0.0.5:41234", "device")]
    assert mod.resolve_serial(None, lambda: devs) == "10.0.0.5:41234"


def test_resolve_serial_exits_when_nothing_attached(monkeypatch):
    monkeypatch.delenv("PELOTON_ADB_SERIAL", raising=False)
    with pytest.raises(SystemExit) as exc:
        mod.resolve_serial(None, lambda: [])
    assert "connect" in str(exc.value).lower()


def test_resolve_serial_exits_when_ambiguous(monkeypatch):
    monkeypatch.delenv("PELOTON_ADB_SERIAL", raising=False)
    devs = [("10.0.0.5:1", "device"), ("10.0.0.6:2", "device")]
    with pytest.raises(SystemExit) as exc:
        mod.resolve_serial(None, lambda: devs)
    assert "-s" in str(exc.value)


# ---------------------------------------------------------------------------
# parse_host_port
# ---------------------------------------------------------------------------


def test_parse_host_port_ok():
    assert mod.parse_host_port("10.0.0.5:41234") == ("10.0.0.5", 41234)


@pytest.mark.parametrize("bad", ["10.0.0.5", "10.0.0.5:", ":5555", "10.0.0.5:abc", "10.0.0.5:0", "10.0.0.5:70000"])
def test_parse_host_port_rejects_malformed(bad):
    with pytest.raises(SystemExit):
        mod.parse_host_port(bad)


# ---------------------------------------------------------------------------
# gate_state: classify the membership-gate package from pm/pidof output
# ---------------------------------------------------------------------------


def test_gate_state_disabled_and_stopped():
    st = mod.gate_state(disabled_pkgs="package:com.onepeloton.systempluginui\n", pid="")
    assert st == "disabled"


def test_gate_state_enabled_running():
    st = mod.gate_state(disabled_pkgs="", pid="8915\n")
    assert st == "enabled (running, pid 8915)"


def test_gate_state_enabled_not_running():
    st = mod.gate_state(disabled_pkgs="", pid="")
    assert st == "enabled (not running)"


def test_gate_state_disabled_but_still_running_is_flagged():
    # pm disable-user without a force-stop leaves the old process alive.
    st = mod.gate_state(disabled_pkgs="package:com.onepeloton.systempluginui\n", pid="8915\n")
    assert st.startswith("disabled") and "still running" in st


# ---------------------------------------------------------------------------
# diagnose_verdict: logcat + pid -> human verdict
# ---------------------------------------------------------------------------

LOG_KILLED = """09-12 16:32:51.815 I/libPowerHal(  343): [perfNotifyAppState] foreground:com.netflix.mediaclient, pid:14393, uid:10086
09-12 16:32:51.882 W/AuthValidator( 8915): No authenticated user found, sending user to login screen
09-12 16:32:51.892 W/ActivityTaskManager(  616): Force removing ActivityRecord{51eb268 u0 com.netflix.mediaclient/.ui.launch.UIWebViewActivity t1679 f}}: app died, no saved state
"""


def test_verdict_membership_gate_when_authvalidator_and_died():
    v = mod.diagnose_verdict("com.netflix.mediaclient", LOG_KILLED, pid="")
    assert v.startswith("KILLED by membership gate")
    assert "AuthValidator" in v


def test_verdict_running_when_pid_alive():
    v = mod.diagnose_verdict("com.netflix.mediaclient", "", pid="14743\n")
    assert v.startswith("RUNNING")


def test_verdict_died_without_gate_signature():
    log = "09-12 W/ActivityTaskManager: Force removing ActivityRecord{x u0 com.foo/.Main}: app died, no saved state\n"
    v = mod.diagnose_verdict("com.foo", log, pid="")
    assert v.startswith("DIED")
    assert "membership gate" not in v


def test_verdict_never_started():
    v = mod.diagnose_verdict("com.foo", "", pid="")
    assert v.startswith("NOT RUNNING")


# ---------------------------------------------------------------------------
# tmux warning: macOS Local Network permission silently blocks LAN from tmux
# ---------------------------------------------------------------------------


def test_tmux_warning_only_on_darwin_inside_tmux(monkeypatch):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1/default,1,0")
    assert mod.tmux_warning(platform="darwin") is not None
    assert mod.tmux_warning(platform="linux") is None
    monkeypatch.delenv("TMUX")
    assert mod.tmux_warning(platform="darwin") is None


# ---------------------------------------------------------------------------
# third_party_packages: strip `package:` prefix, sorted
# ---------------------------------------------------------------------------


def test_third_party_packages_parses_and_sorts():
    out = "package:com.netflix.mediaclient\npackage:app.lawnchair\n\n"
    assert mod.third_party_packages(out) == ["app.lawnchair", "com.netflix.mediaclient"]
