---
name: macos-desktop-control
description: Use on macOS when Claude needs to take a screenshot of the desktop, click at a specific coordinate, double-click, or type text into a native dialog — anywhere a browser-based tool (Playwright) can't reach. macOS-only. Requires `cliclick` for click and type subcommands (brew install cliclick).
---

# macOS Desktop Control

Capture screenshots and drive the macOS desktop with clicks and keystrokes. Useful for the cases where Playwright doesn't reach — native dialogs, system prompts, menu bar actions, full-screen apps.

## When to use

- A flow needs interaction with a macOS dialog (Login Items prompt, sandboxed save panel) — Playwright can't see it.
- You need a quick screenshot of the whole desktop, not a specific app window.
- A scripted test needs to send keystrokes to a focused, non-browser app.

## When NOT to use

- The target is a web app — use Playwright MCP. It's safer and more reliable than coordinate-based clicking.
- You're on Linux or Windows — this skill is macOS-only.
- You don't know the screen coordinates and there's no way to find them — coordinate-based control is brittle. Take a screenshot first, identify the target visually, then click.
- The action is destructive (Cmd-Q, "Move to Trash" confirmation). Stop and ask.

## Setup (one time)

```bash
brew install cliclick     # only needed for click / type
```

`screencapture` ships with macOS. macOS will prompt for **Accessibility** and **Screen Recording** permissions the first time `cliclick` or `screencapture` runs from your terminal — grant them in System Settings → Privacy & Security.

## Invoke

```bash
# Save a screenshot to a path (useful — keeps the image around so you can re-read it)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/macos-desktop-control/scripts/desktop.py" take --output /tmp/desktop.png

# Print as base64 (mirrors the original MCP image-content behavior)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/macos-desktop-control/scripts/desktop.py" take --base64

# Click and type
python3 "${CLAUDE_PLUGIN_ROOT}/skills/macos-desktop-control/scripts/desktop.py" click 500 320
python3 "${CLAUDE_PLUGIN_ROOT}/skills/macos-desktop-control/scripts/desktop.py" double-click 500 320
python3 "${CLAUDE_PLUGIN_ROOT}/skills/macos-desktop-control/scripts/desktop.py" type "hello world"
```

### Subcommands

| Subcommand | What it does |
|---|---|
| `take [--output PATH] [--base64]` | Capture the full desktop (`screencapture -x`). Default prints the temp-file path. `--output` writes to a chosen location. `--base64` prints PNG bytes as base64 to stdout. |
| `click X Y` | Single left click at pixel coordinates. |
| `double-click X Y` | Double click at pixel coordinates. |
| `type "text"` | Type text into the focused window using `cliclick t:`. |

## Workflow tip

For visual tasks, alternate `take → identify coordinates from screenshot → click → take` rather than chaining multiple blind clicks. A wrong click is easy to recover from if you screenshot between actions; a chain of wrong clicks is not.

## Rules

- **Confirm before destructive actions.** Cmd-Q on an unsaved doc, "Move to Trash" confirmations, "Allow Always" permission grants — stop and check with the user.
- **Take a screenshot before any non-trivial click.** "I think the button is around (500, 320)" is a recipe for clicking the wrong thing. Verify first.
- **Don't type passwords with `type`.** The text is visible as text in the command, and macOS may handle paste differently in secure inputs. Direct the user to a password manager (`bitwarden-vault`) or fill via the keyboard themselves.
- **Coordinate brittleness.** Coordinates are tied to the user's resolution and window arrangement. Anything you script today can break tomorrow. Prefer Playwright for web; reserve this skill for the cases Playwright can't reach.
