---
name: sideloading-peloton-apps
description: Use when installing, launching, or un-breaking third-party apps (Netflix, Disney+, Zwift, a launcher, Aurora Store) on a Peloton Bike/Bike+/Tread tablet over Wi-Fi ADB — including when a sideloaded app closes within a second after a reboot with a "must be logged in to a Peloton membership" toast, when `adb connect` to the bike hangs or times out, or when the wireless-debugging port keeps changing.
---

# Sideloading Peloton apps

The Peloton tablet is a locked-down Android device (Android 11 on Bike+/Tread-class hardware; Gen-1 Bikes are much older). Developer mode + wireless debugging give you a normal `adb`, and everything below is done with `adb` from a laptop on the same LAN. No root, and every device change here is reversible.

Bundled helper (stdlib Python, wraps `adb`):

```bash
PELO="python3 ${CLAUDE_PLUGIN_ROOT}/skills/sideloading-peloton-apps/scripts/peloton_adb.py"
$PELO --help
```

`CLAUDE_PLUGIN_ROOT` only exists inside a Claude Code session. In a plain shell use the absolute path (`find ~/.claude/plugins -name peloton_adb.py`), or run the underlying `adb` commands shown in this doc directly.

## When to use

- "Put Netflix / Disney+ / Zwift on my Peloton" or "install this APK on the bike".
- Sideloaded apps used to work, the bike rebooted, and now they die on launch with a Peloton membership toast.
- `adb connect <bike-ip>:<port>` hangs, times out, or the port on the Wireless debugging screen changed.
- Sideloaded apps are installed but nowhere to be found on the Peloton home screen.

## When NOT to use

- The user wants Peloton's own classes/entertainment tab fixed — that is a Peloton account/support issue.
- Anything that needs root, a custom ROM, or uninstalling Peloton system packages. Don't: `com.onepeloton.affernetservice` is the bike's sensor driver, and OpenPelo-style "uninstall Peloton services" tooling can leave the tablet needing a factory reset.

## Connect (every time — wireless debugging turns itself off on reboot)

1. On the bike: Settings → System → Developer options (tap Build number 7× under About tablet if missing) → **Wireless debugging** → on. Read the `IP:port` shown there. It is a new random port every time.
2. First time on this laptop only: tap **Pair device with pairing code**, then `$PELO connect <ip>:<port> --pair <ip>:<pairport> --code <6 digits>`. Pairing is keyed to the laptop's adb key and the bike's certificate, not to the port, so it survives the bike rebooting and the port changing. On later days just:

```bash
$PELO connect <ip>:<port>
$PELO status            # OS/build, home app, gate state, third-party packages
```

3. Optional, until the next reboot: `$PELO stable-port` flips adbd to port 5555 so the address stops changing mid-session.

**macOS + tmux gotcha:** macOS Local Network permission is granted per "responsible process". A daemonized tmux server is silently denied, so from inside tmux the router pings but the bike never answers and its ARP entry stays `(incomplete)`. Run the adb commands from a plain terminal window (or start the adb server from one; clients in tmux then talk to it over localhost). The helper prints a warning when it detects this.

## Install and launch

```bash
$PELO install ./lawnchair.apk ./aurora.apk     # adb install -r, each
$PELO launch com.aurora.store
```

- Sideloaded apps do **not** appear on the Peloton home screen. Install a launcher (Lawnchair, Nova) and pick it when you tap the Peloton logo/home button; switch the home app back to Peloton when you want Peloton's UI.
- Aurora Store (F-Droid APK) installs Play-store apps without Google services. Netflix installs from there as `com.netflix.mediaclient` and plays fine without GMS.
- Storage is tight (4 GB class). Check `adb shell df -h /data` before piling on apps.

## The membership gate (the "logged in Peloton membership" toast)

Since a late-2025 Peloton update, the vendor app **`com.onepeloton.systempluginui`** ("System Plugin UI") holds `FORCE_STOP_PACKAGES` + `SYSTEM_ALERT_WINDOW`. Whenever a third-party app reaches the foreground, its `AuthValidator` checks for a logged-in Peloton user; with none it force-stops the app within ~100 ms and shows the toast. It is armed at boot, which is why a setup that "worked" can die after the first reboot. Signature in `logcat`:

```
W/AuthValidator( <pid>): No authenticated user found, sending user to login screen
W/ActivityTaskManager: Force removing ActivityRecord{... com.netflix.mediaclient/...}: app died
```

Confirm before fixing — a gate that isn't there is a different bug:

```bash
$PELO diagnose com.netflix.mediaclient    # launches it, reads logcat, prints a verdict
```

Fix (persists across reboots, reversible):

```bash
$PELO unblock     # pm disable-user --user 0 com.onepeloton.systempluginui + force-stop
$PELO reblock     # pm enable — undo
```

Alternatives: sign in to the Peloton app with an active membership (the gate is satisfied, nothing disabled), or force-stop Peloton, Peloton Diagnostic Service, and System Plugin UI App from Settings after each boot (temporary). A Peloton OTA can re-enable the package; if the toast returns, run `diagnose` then `unblock` again.

## Quick reference

| Symptom | Cause | Do |
|---|---|---|
| App dies <1 s after launch, membership toast | `systempluginui` gate armed | `diagnose` → `unblock` |
| `adb connect` hangs; router pings, bike doesn't | macOS Local Network vs tmux | Plain terminal, not tmux |
| `failed to connect ... Connection refused` | Wireless debugging off / port changed | Toggle it on, re-read `IP:port` |
| `adb devices` shows `unauthorized` | New laptop key | Accept the trust dialog on the bike |
| Apps installed but invisible | Peloton home hides them | Install a launcher, set it as home |
| Worked for weeks, then stopped | Peloton OTA re-enabled the gate / removed apps | `status`, re-`unblock`, reinstall |

## Rules

- Read-first: run `status`/`diagnose` before changing anything; `unblock` refuses to report success unless `pm list packages -d` shows the package disabled.
- Only `pm disable-user` the gate package. Never `pm uninstall` Peloton packages; never touch `affernetservice`.
- Don't put a real bike's IP, serial, or pairing name in docs or commits — they're LAN-specific and personal.
