#!/usr/bin/env python3
"""Bitwarden CLI wrapper.

Ported from a TypeScript MCP server (apps/mcp-servers/bitwarden/src/index.ts).
Shells out to the `bw` CLI. Requires:
  - Bitwarden CLI installed (https://bitwarden.com/help/cli/)
  - BW_SESSION in the environment (from `bw unlock`)

Cache caveat: bw keeps a local cache. Run `bitwarden.py sync` after creating
or editing items, and before listing/searching if recent changes may have
been made from another machine.

Usage:
  bitwarden.py status
  bitwarden.py sync
  bitwarden.py list-items [--search TERM] [--folder-id ID] [--collection-id ID]
  bitwarden.py get-item IDENTIFIER
  bitwarden.py create-item NAME [--username U] [--password P] [--uri URL] [--notes N] [--folder-id F]
  bitwarden.py edit-item ID [--name N] [--username U] [--password P] [--uri URL] [--notes N]
  bitwarden.py delete-item ID
  bitwarden.py generate-password [--length 20] [--no-uppercase] [--no-lowercase] [--no-numbers] [--no-special]
  bitwarden.py list-folders
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from typing import Any

TYPE_NAMES = {1: "login", 2: "secure_note", 3: "card", 4: "identity"}


def get_session() -> str:
    session = os.environ.get("BW_SESSION")
    if not session:
        sys.exit(
            "BW_SESSION environment variable is not set. "
            "Run `bw unlock` and export the BW_SESSION it prints."
        )
    return session


def bw(*args: str) -> str:
    session = get_session()
    full = ["bw", *args, "--session", session]
    env = {**os.environ, "BW_SESSION": session}
    try:
        result = subprocess.run(
            full, capture_output=True, text=True, env=env, timeout=30
        )
    except subprocess.TimeoutExpired:
        sys.exit("bw timed out after 30s")
    except FileNotFoundError:
        sys.exit(
            "`bw` not found on PATH. Install the Bitwarden CLI: "
            "https://bitwarden.com/help/cli/"
        )

    out = result.stdout.strip()
    if result.returncode != 0:
        msg = result.stderr.strip() or out or "(no output)"
        sys.exit(f"bw error: {msg}")
    return out


def format_item(item: dict[str, Any], include_password: bool = False) -> str:
    type_name = TYPE_NAMES.get(item.get("type", 0), "unknown")
    lines = [f"**{item['name']}** ({type_name}) [id: {item['id']}]"]
    login = item.get("login") or {}
    if login.get("username"):
        lines.append(f"  Username: {login['username']}")
    if include_password and login.get("password"):
        lines.append(f"  Password: {login['password']}")
    uris = login.get("uris") or []
    if uris:
        lines.append(f"  URLs: {', '.join(u['uri'] for u in uris if u.get('uri'))}")
    notes = item.get("notes")
    if notes:
        lines.append(f"  Notes: {notes[:200]}")
    if item.get("folderId"):
        lines.append(f"  Folder: {item['folderId']}")
    return "\n".join(lines)


def cmd_status(_args: argparse.Namespace) -> None:
    print(bw("status"))


def cmd_sync(_args: argparse.Namespace) -> None:
    bw("sync")
    print("Vault synced.")


def cmd_list_items(args: argparse.Namespace) -> None:
    cmd = ["list", "items"]
    if args.search:
        cmd += ["--search", args.search]
    if args.folder_id:
        cmd += ["--folderid", args.folder_id]
    if args.collection_id:
        cmd += ["--collectionid", args.collection_id]
    items = json.loads(bw(*cmd))
    if not items:
        print("No items found.")
        return
    body = "\n\n".join(format_item(i, False) for i in items)
    print(f"Found {len(items)} item(s):\n\n{body}")


def cmd_get_item(args: argparse.Namespace) -> None:
    item = json.loads(bw("get", "item", args.identifier))
    print(format_item(item, include_password=True))


def cmd_create_item(args: argparse.Namespace) -> None:
    template = json.loads(bw("get", "template", "item"))
    template["name"] = args.name
    template["type"] = 1  # login
    template["notes"] = args.notes
    template["folderId"] = args.folder_id

    login_template = json.loads(bw("get", "template", "item.login"))
    login_template["username"] = args.username
    login_template["password"] = args.password
    login_template["uris"] = (
        [{"match": None, "uri": args.uri}] if args.uri else []
    )
    template["login"] = login_template

    encoded = base64.b64encode(json.dumps(template).encode("utf-8")).decode(
        "ascii"
    )
    created = json.loads(bw("create", "item", encoded))
    print(f"Created item: {format_item(created, False)}")


def cmd_edit_item(args: argparse.Namespace) -> None:
    item = json.loads(bw("get", "item", args.id))

    has_login_changes = (
        args.username is not None
        or args.password is not None
        or args.uri is not None
    )
    if has_login_changes and item.get("type") != 1:
        sys.exit("Cannot set login fields on non-login items")

    if args.name is not None:
        item["name"] = args.name
    if args.notes is not None:
        item["notes"] = args.notes
    if has_login_changes:
        login = item.get("login") or {}
        if args.username is not None:
            login["username"] = args.username
        if args.password is not None:
            login["password"] = args.password
        if args.uri is not None:
            login["uris"] = [{"match": None, "uri": args.uri}]
        item["login"] = login

    encoded = base64.b64encode(json.dumps(item).encode("utf-8")).decode("ascii")
    updated = json.loads(bw("edit", "item", args.id, encoded))
    print(f"Updated item: {format_item(updated, False)}")


def cmd_delete_item(args: argparse.Namespace) -> None:
    bw("delete", "item", args.id)
    print(f"Deleted item {args.id}")


def cmd_generate_password(args: argparse.Namespace) -> None:
    cmd = ["generate", "--length", str(args.length)]
    if not args.no_uppercase:
        cmd.append("--uppercase")
    if not args.no_lowercase:
        cmd.append("--lowercase")
    if not args.no_numbers:
        cmd.append("--number")
    if not args.no_special:
        cmd.append("--special")
    print(bw(*cmd))


def cmd_list_folders(_args: argparse.Namespace) -> None:
    folders = json.loads(bw("list", "folders"))
    if not folders:
        print("No folders.")
        return
    print("\n".join(f"- **{f['name']}** [{f['id']}]" for f in folders))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bitwarden.py",
        description=(
            "Bitwarden CLI wrapper. IMPORTANT: run sync after creating/editing "
            "items, and before listing/searching if recent changes may exist on "
            "another machine. The local cache is not auto-updated."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Vault status (locked/unlocked, last sync).")
    sub.add_parser("sync", help="Sync local cache with the Bitwarden server.")

    p = sub.add_parser("list-items", help="List vault items.")
    p.add_argument("--search", help="Search term to filter items.")
    p.add_argument("--folder-id", help="Filter by folder ID.")
    p.add_argument("--collection-id", help="Filter by collection ID.")

    p = sub.add_parser("get-item", help="Get one item by ID or exact name.")
    p.add_argument("identifier", help="Item ID or exact name.")

    p = sub.add_parser("create-item", help="Create a new login item.")
    p.add_argument("name", help="Name of the item.")
    p.add_argument("--username", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--uri", default=None, help="Login URL.")
    p.add_argument("--notes", default=None)
    p.add_argument("--folder-id", default=None)

    p = sub.add_parser("edit-item", help="Edit an existing item.")
    p.add_argument("id", help="Item ID to edit.")
    p.add_argument("--name", default=None)
    p.add_argument("--username", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--uri", default=None)
    p.add_argument("--notes", default=None)

    p = sub.add_parser("delete-item", help="Delete an item (moves to trash).")
    p.add_argument("id", help="Item ID to delete.")

    p = sub.add_parser(
        "generate-password", help="Generate a secure password."
    )
    p.add_argument("--length", type=int, default=20)
    p.add_argument("--no-uppercase", action="store_true")
    p.add_argument("--no-lowercase", action="store_true")
    p.add_argument("--no-numbers", action="store_true")
    p.add_argument("--no-special", action="store_true")

    sub.add_parser("list-folders", help="List all folders in the vault.")

    args = parser.parse_args()

    dispatch = {
        "status": cmd_status,
        "sync": cmd_sync,
        "list-items": cmd_list_items,
        "get-item": cmd_get_item,
        "create-item": cmd_create_item,
        "edit-item": cmd_edit_item,
        "delete-item": cmd_delete_item,
        "generate-password": cmd_generate_password,
        "list-folders": cmd_list_folders,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
