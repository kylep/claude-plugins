#!/usr/bin/env python3
"""macOS desktop control: screenshot, click, double-click, type text.

Ported from a TypeScript MCP server (apps/mcp-servers/screenshot/src/index.ts).
macOS-only. Uses `screencapture` (built-in) and `cliclick`
(https://github.com/BlueM/cliclick — install with `brew install cliclick`).

Usage:
  desktop.py take [--output PATH] [--base64]
  desktop.py click X Y
  desktop.py double-click X Y
  desktop.py type "text to enter"
"""

from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
import tempfile


def require_macos() -> None:
    if sys.platform != "darwin":
        sys.exit(
            f"This script is macOS-only (current platform: {sys.platform})."
        )


def run(*cmd: str) -> None:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        sys.exit(
            f"`{cmd[0]}` not found on PATH. "
            "Install cliclick with `brew install cliclick`."
        )
    except subprocess.TimeoutExpired:
        sys.exit(f"{cmd[0]} timed out after 30s")
    if result.returncode != 0:
        msg = result.stderr.strip() or "(no stderr)"
        sys.exit(f"{cmd[0]} failed: {msg}")


def cmd_take(args: argparse.Namespace) -> None:
    require_macos()
    if args.output:
        path = args.output
        cleanup = False
    else:
        fd, path = tempfile.mkstemp(prefix="screenshot-", suffix=".png")
        os.close(fd)
        cleanup = True
    try:
        run("screencapture", "-x", path)
        if args.base64:
            with open(path, "rb") as f:
                sys.stdout.write(base64.b64encode(f.read()).decode("ascii"))
                sys.stdout.write("\n")
        else:
            print(path)
    finally:
        if cleanup and not args.base64:
            # if not base64, the user got the path; leave the file in place
            pass
        elif cleanup:
            os.unlink(path)


def cmd_click(args: argparse.Namespace) -> None:
    require_macos()
    run("cliclick", f"c:{args.x},{args.y}")
    print(f"Clicked at ({args.x}, {args.y})")


def cmd_double_click(args: argparse.Namespace) -> None:
    require_macos()
    run("cliclick", f"dc:{args.x},{args.y}")
    print(f"Double-clicked at ({args.x}, {args.y})")


def cmd_type(args: argparse.Namespace) -> None:
    require_macos()
    run("cliclick", f"t:{args.text}")
    print(f"Typed: {args.text}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="desktop.py",
        description="macOS desktop control: screenshot, click, type.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    take = sub.add_parser("take", help="Capture the macOS desktop.")
    take.add_argument(
        "--output",
        help=(
            "Write the PNG to this path. If omitted with --base64, writes to "
            "a temp file and deletes it after encoding."
        ),
    )
    take.add_argument(
        "--base64",
        action="store_true",
        help="Print the PNG as base64-encoded text (mirrors the original MCP behavior).",
    )

    click = sub.add_parser("click", help="Click at (X, Y).")
    click.add_argument("x", type=int, help="X coordinate (pixels from left).")
    click.add_argument("y", type=int, help="Y coordinate (pixels from top).")

    dclick = sub.add_parser("double-click", help="Double-click at (X, Y).")
    dclick.add_argument("x", type=int)
    dclick.add_argument("y", type=int)

    typ = sub.add_parser("type", help="Type text using the keyboard.")
    typ.add_argument("text", help="Text to type.")

    args = parser.parse_args()
    {
        "take": cmd_take,
        "click": cmd_click,
        "double-click": cmd_double_click,
        "type": cmd_type,
    }[args.command](args)


if __name__ == "__main__":
    main()
