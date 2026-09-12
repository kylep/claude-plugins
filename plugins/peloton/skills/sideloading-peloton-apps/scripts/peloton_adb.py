#!/usr/bin/env python3
"""Wireless-ADB helper for sideloading apps onto a Peloton tablet.

Thin wrapper over the `adb` binary from Android platform-tools. Stdlib only.
Nothing here needs root; every device change is reversible.

Usage:
  peloton_adb.py connect HOST:PORT [--pair HOST:PAIRPORT --code 123456]
  peloton_adb.py stable-port [--port 5555]
  peloton_adb.py status
  peloton_adb.py packages
  peloton_adb.py install APK [APK ...]
  peloton_adb.py launch PACKAGE
  peloton_adb.py diagnose PACKAGE [--wait SECONDS]
  peloton_adb.py unblock            # disable Peloton's membership gate
  peloton_adb.py reblock            # re-enable it

Device selection: `-s SERIAL`, else $PELOTON_ADB_SERIAL, else the single
attached device.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

# Peloton's "System Plugin UI" vendor app. Its AuthValidator force-stops any
# third-party app that reaches the foreground when no Peloton user is logged
# in (the "must be logged in to a Peloton membership" toast). It holds
# FORCE_STOP_PACKAGES + SYSTEM_ALERT_WINDOW, which is how it does both.
GATE_PACKAGE = "com.onepeloton.systempluginui"

ADB_TIMEOUT = 60


# ---------------------------------------------------------------------------
# adb plumbing
# ---------------------------------------------------------------------------


def adb(*args: str, serial: str | None = None, check: bool = True) -> str:
    """Run adb and return stdout (+stderr) as text."""
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=ADB_TIMEOUT)
    except FileNotFoundError:
        sys.exit("`adb` not found on PATH. Install Android platform-tools "
                 "(e.g. `brew install --cask android-platform-tools`).")
    except subprocess.TimeoutExpired:
        sys.exit(f"adb {' '.join(args)} timed out after {ADB_TIMEOUT}s. "
                 "Is wireless debugging still on and the bike awake?")
    out = (res.stdout or "") + (res.stderr or "")
    if check and res.returncode != 0:
        sys.exit(f"adb {' '.join(args)} failed: {out.strip() or '(no output)'}")
    return out


def shell(serial: str, command: str) -> str:
    """Run a single shell command on the device; never fails on exit code
    (many `pm`/`pidof` calls use non-zero to mean "no result")."""
    return adb("shell", *command.split(" "), serial=serial, check=False)


def parse_devices(text: str) -> list[tuple[str, str]]:
    """`adb devices -l` output -> [(serial, state)]."""
    devs = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devs.append((parts[0], parts[1]))
    return devs


def list_devices() -> list[tuple[str, str]]:
    return parse_devices(adb("devices", "-l", check=False))


def resolve_serial(explicit: str | None, devices=list_devices) -> str:
    """Explicit flag > $PELOTON_ADB_SERIAL > the one online device."""
    if explicit:
        return explicit
    env = os.environ.get("PELOTON_ADB_SERIAL")
    if env:
        return env
    online = [s for s, state in devices() if state == "device"]
    if not online:
        sys.exit("No device attached. Run `connect HOST:PORT` first "
                 "(read HOST:PORT from the bike's Wireless debugging screen).")
    # Wireless debugging advertises the same bike as ip:port and as an mDNS
    # alias; prefer ip:port, which is what `adb tcpip` keeps working.
    ip_port = [s for s in online if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", s)]
    if len(ip_port) == 1:
        return ip_port[0]
    if len(online) == 1:
        return online[0]
    sys.exit("More than one device attached; pick one with -s SERIAL "
             f"(attached: {', '.join(online)}).")


def parse_host_port(value: str) -> tuple[str, int]:
    m = re.match(r"^([^:\s]+):(\d+)$", value or "")
    if not m or not 0 < int(m.group(2)) < 65536:
        sys.exit(f"Expected HOST:PORT, got {value!r}.")
    return m.group(1), int(m.group(2))


def tmux_warning(platform: str = sys.platform) -> str | None:
    """macOS's Local Network privacy permission silently drops LAN traffic
    from processes whose responsible process is a daemonized tmux server.
    Symptom: gateway pings fine, the bike's ARP entry stays incomplete."""
    if platform == "darwin" and os.environ.get("TMUX"):
        return ("Running inside tmux on macOS: Local Network permission may "
                "silently block the bike. If connect hangs or times out, run "
                "this from a plain terminal window (not tmux).")
    return None


# ---------------------------------------------------------------------------
# pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def third_party_packages(pm_output: str) -> list[str]:
    pkgs = [l.strip()[len("package:"):] for l in pm_output.splitlines()
            if l.strip().startswith("package:")]
    return sorted(pkgs)


def gate_state(disabled_pkgs: str, pid: str) -> str:
    disabled = f"package:{GATE_PACKAGE}" in disabled_pkgs
    pid = pid.strip()
    if disabled and pid:
        return f"disabled (but still running, pid {pid}; force-stop it)"
    if disabled:
        return "disabled"
    if pid:
        return f"enabled (running, pid {pid})"
    return "enabled (not running)"


def diagnose_verdict(package: str, logcat: str, pid: str) -> str:
    if pid.strip():
        return f"RUNNING (pid {pid.strip()}) — {package} survived the foreground check."
    died = re.search(rf"{re.escape(package)}\S*.*app died", logcat) is not None
    auth = "AuthValidator" in logcat and "No authenticated user" in logcat
    if died and auth:
        return (f"KILLED by membership gate: {GATE_PACKAGE} (AuthValidator: "
                f"'No authenticated user found') force-stopped {package} on "
                "launch. Fix: `unblock`, or sign in to the Peloton app.")
    if died:
        return f"DIED: {package} exited but no membership-gate signature in logcat; check the app itself."
    return f"NOT RUNNING: {package} never came up. Is it installed? (`packages`)"


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def cmd_connect(args: argparse.Namespace) -> None:
    warn = tmux_warning()
    if warn:
        print(warn, file=sys.stderr)
    parse_host_port(args.target)
    if args.pair:
        if not args.code:
            sys.exit("--pair needs --code (the 6-digit Wi-Fi pairing code).")
        parse_host_port(args.pair)
        out = adb("pair", args.pair, args.code, check=False)
        print(out.strip())
        if "Successfully paired" not in out:
            sys.exit("Pairing failed; check the code and pairing port (they change every time the dialog opens).")
    out = adb("connect", args.target, check=False)
    print(out.strip())
    if not out.startswith("connected to") and "already connected" not in out:
        sys.exit(f"connect failed: {out.strip()}")


def cmd_stable_port(args: argparse.Namespace) -> None:
    serial = resolve_serial(args.serial)
    host, _ = parse_host_port(serial)
    print(adb("tcpip", str(args.port), serial=serial, check=False).strip())
    time.sleep(2)
    out = adb("connect", f"{host}:{args.port}", check=False)
    print(out.strip())
    if not out.startswith("connected to") and "already connected" not in out:
        sys.exit(f"reconnect on port {args.port} failed: {out.strip()}")
    print(f"Use -s {host}:{args.port} (or export PELOTON_ADB_SERIAL) until the next reboot.")


def _gate_state(serial: str) -> str:
    return gate_state(shell(serial, "pm list packages -d"),
                      shell(serial, f"pidof {GATE_PACKAGE}"))


def cmd_status(args: argparse.Namespace) -> None:
    serial = resolve_serial(args.serial)
    rel = shell(serial, "getprop ro.build.version.release").strip()
    build = shell(serial, "getprop ro.build.display.id").strip()
    model = shell(serial, "getprop ro.product.model").strip()
    wifi_dbg = shell(serial, "settings get global adb_wifi_enabled").strip()
    home = shell(serial, "cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME")
    home_pkg = next((l.strip() for l in home.splitlines() if "/" in l), home.strip().splitlines()[-1] if home.strip() else "?")
    pkgs = third_party_packages(shell(serial, "pm list packages -3"))
    print(f"device        {serial}  model {model}  Android {rel}  build {build}")
    print(f"wireless dbg  {'on' if wifi_dbg == '1' else 'off/unknown (' + wifi_dbg + ')'}")
    print(f"home app      {home_pkg}")
    print(f"gate          {GATE_PACKAGE}: {_gate_state(serial)}")
    print("third-party   " + (", ".join(pkgs) if pkgs else "(none)"))


def cmd_packages(args: argparse.Namespace) -> None:
    serial = resolve_serial(args.serial)
    for p in third_party_packages(shell(serial, "pm list packages -3")):
        print(p)


def cmd_install(args: argparse.Namespace) -> None:
    for apk in args.apk:
        if not os.path.isfile(apk):
            sys.exit(f"APK not found: {apk}")
    serial = resolve_serial(args.serial)
    for apk in args.apk:
        out = adb("install", "-r", apk, serial=serial, check=False)
        line = out.strip().splitlines()[-1] if out.strip() else "(no output)"
        print(f"{os.path.basename(apk)}: {line}")
        if "Success" not in out:
            sys.exit(f"install failed for {apk}")


def _launch(serial: str, package: str) -> str:
    return shell(serial, f"monkey -p {package} -c android.intent.category.LAUNCHER 1")


def cmd_launch(args: argparse.Namespace) -> None:
    serial = resolve_serial(args.serial)
    out = _launch(serial, args.package)
    print(out.strip().splitlines()[0] if out.strip() else "launched")


def cmd_diagnose(args: argparse.Namespace) -> None:
    serial = resolve_serial(args.serial)
    shell(serial, "logcat -c")
    _launch(serial, args.package)
    time.sleep(args.wait)
    pid = shell(serial, f"pidof {args.package}")
    log = shell(serial, "logcat -d -v time")
    print(diagnose_verdict(args.package, log, pid))
    hits = [l for l in log.splitlines() if "AuthValidator" in l or (args.package in l and "app died" in l)]
    for l in hits[:6]:
        print("  " + l.strip())
    print(f"gate: {_gate_state(serial)}")


def cmd_unblock(args: argparse.Namespace) -> None:
    serial = resolve_serial(args.serial)
    print(shell(serial, f"pm disable-user --user 0 {GATE_PACKAGE}").strip())
    shell(serial, f"am force-stop {GATE_PACKAGE}")
    state = _gate_state(serial)
    if not state.startswith("disabled"):
        sys.exit(f"{GATE_PACKAGE} is still enabled ({state}); the disable did not stick.")
    print(f"{GATE_PACKAGE}: {state}. Third-party apps can run without a Peloton login. "
          "Survives reboots; a Peloton OTA may re-enable it (re-run `unblock`). Undo with `reblock`.")


def cmd_reblock(args: argparse.Namespace) -> None:
    serial = resolve_serial(args.serial)
    print(shell(serial, f"pm enable --user 0 {GATE_PACKAGE}").strip())
    print(f"{GATE_PACKAGE}: {_gate_state(serial)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-s", "--serial", help="adb serial (HOST:PORT); default $PELOTON_ADB_SERIAL or the only attached device")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("connect", help="connect over wireless debugging (optionally pair first)")
    c.add_argument("target", help="HOST:PORT shown on the Wireless debugging screen")
    c.add_argument("--pair", metavar="HOST:PAIRPORT", help="pairing address from 'Pair device with pairing code'")
    c.add_argument("--code", help="6-digit pairing code")
    c.set_defaults(fn=cmd_connect)

    s = sub.add_parser("stable-port", help="switch adbd to a fixed TCP port until next reboot")
    s.add_argument("--port", type=int, default=5555)
    s.set_defaults(fn=cmd_stable_port)

    sub.add_parser("status", help="OS/build, home app, gate state, third-party packages").set_defaults(fn=cmd_status)
    sub.add_parser("packages", help="list third-party packages").set_defaults(fn=cmd_packages)

    i = sub.add_parser("install", help="adb install -r one or more APKs")
    i.add_argument("apk", nargs="+")
    i.set_defaults(fn=cmd_install)

    l = sub.add_parser("launch", help="launch a package's LAUNCHER activity")
    l.add_argument("package")
    l.set_defaults(fn=cmd_launch)

    d = sub.add_parser("diagnose", help="launch a package and report whether the membership gate killed it")
    d.add_argument("package")
    d.add_argument("--wait", type=float, default=5.0, help="seconds to wait before checking (default 5)")
    d.set_defaults(fn=cmd_diagnose)

    sub.add_parser("unblock", help=f"pm disable-user {GATE_PACKAGE} (reversible)").set_defaults(fn=cmd_unblock)
    sub.add_parser("reblock", help=f"pm enable {GATE_PACKAGE}").set_defaults(fn=cmd_reblock)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
