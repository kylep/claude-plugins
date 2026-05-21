#!/usr/bin/env python3
"""Discord bot CLI.

Ported from a Python MCP server (apps/mcp-servers/discord/server.py).
Calls the Discord REST API v10. Requires:
  DISCORD_BOT_TOKEN  — bot token from the Discord Developer Portal
  DISCORD_GUILD_ID   — optional default guild for `list-channels` without args

Usage:
  discord.py list-guilds
  discord.py list-channels [--guild-id ID]
  discord.py get-channel-info CHANNEL_ID
  discord.py send-message CHANNEL_ID "text"
  discord.py read-messages CHANNEL_ID [--limit 10]
  discord.py reply CHANNEL_ID MESSAGE_ID "text"
  discord.py edit-message CHANNEL_ID MESSAGE_ID "text"
  discord.py delete-message CHANNEL_ID MESSAGE_ID
  discord.py add-reaction CHANNEL_ID MESSAGE_ID EMOJI
  discord.py create-thread CHANNEL_ID MESSAGE_ID "thread name"
  discord.py list-threads CHANNEL_ID
  discord.py search-messages CHANNEL_ID "query" [--limit 25]
  discord.py send-embed CHANNEL_ID "title" "description" [--color INT] [--url URL]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/kpericak, 1.0)"
MAX_MESSAGE_LEN = 2000


def get_token() -> str:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        sys.exit("DISCORD_BOT_TOKEN environment variable is not set")
    return token


def request(
    method: str,
    path: str,
    body: dict | None = None,
    params: dict | None = None,
) -> Any:
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bot {get_token()}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return None
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        sys.exit(f"Discord API error {e.code}: {body_text}")


def check_len(text: str) -> None:
    if len(text) > MAX_MESSAGE_LEN:
        sys.exit(f"Error: message exceeds {MAX_MESSAGE_LEN} character limit.")


def cmd_list_guilds(_args: argparse.Namespace) -> None:
    guilds = request("GET", "/users/@me/guilds")
    if not guilds:
        print("Bot has not joined any servers.")
        return
    for g in guilds:
        print(f"- {g['name']}  (id: {g['id']})")


def cmd_list_channels(args: argparse.Namespace) -> None:
    gid = args.guild_id or os.environ.get("DISCORD_GUILD_ID", "")
    if not gid:
        sys.exit("Provide --guild-id or set DISCORD_GUILD_ID.")
    channels = request("GET", f"/guilds/{gid}/channels")
    text = [c for c in channels if c.get("type") in (0, 5)]
    if not text:
        print("No text channels found.")
        return
    text.sort(key=lambda c: c.get("position", 0))
    for c in text:
        print(f"- #{c['name']}  (id: {c['id']})")


def cmd_get_channel_info(args: argparse.Namespace) -> None:
    c = request("GET", f"/channels/{args.channel_id}")
    lines = [
        f"Name: #{c.get('name', 'DM')}",
        f"ID: {c['id']}",
        f"Type: {c.get('type')}",
    ]
    if c.get("topic"):
        lines.append(f"Topic: {c['topic']}")
    if c.get("guild_id"):
        lines.append(f"Guild ID: {c['guild_id']}")
    print("\n".join(lines))


def cmd_send_message(args: argparse.Namespace) -> None:
    check_len(args.content)
    data = request(
        "POST",
        f"/channels/{args.channel_id}/messages",
        body={"content": args.content, "flags": 4},
    )
    print(f"Sent message {data['id']} in #{args.channel_id}")


def cmd_read_messages(args: argparse.Namespace) -> None:
    limit = max(1, min(100, args.limit))
    msgs = request(
        "GET",
        f"/channels/{args.channel_id}/messages",
        params={"limit": limit},
    )
    if not msgs:
        print("No messages found.")
        return
    for msg in reversed(msgs):
        author = msg["author"]["username"]
        content = msg["content"] or "[embed/attachment]"
        print(f"[{msg['id']}] {author}: {content}")


def cmd_reply(args: argparse.Namespace) -> None:
    check_len(args.content)
    data = request(
        "POST",
        f"/channels/{args.channel_id}/messages",
        body={
            "content": args.content,
            "message_reference": {"message_id": args.message_id},
        },
    )
    print(f"Replied with message {data['id']}")


def cmd_edit_message(args: argparse.Namespace) -> None:
    check_len(args.content)
    request(
        "PATCH",
        f"/channels/{args.channel_id}/messages/{args.message_id}",
        body={"content": args.content},
    )
    print(f"Edited message {args.message_id}")


def cmd_delete_message(args: argparse.Namespace) -> None:
    request("DELETE", f"/channels/{args.channel_id}/messages/{args.message_id}")
    print(f"Deleted message {args.message_id}")


def cmd_add_reaction(args: argparse.Namespace) -> None:
    encoded = quote(args.emoji)
    request(
        "PUT",
        f"/channels/{args.channel_id}/messages/{args.message_id}/reactions/{encoded}/@me",
    )
    print(f"Reacted with {args.emoji}")


def cmd_create_thread(args: argparse.Namespace) -> None:
    data = request(
        "POST",
        f"/channels/{args.channel_id}/messages/{args.message_id}/threads",
        body={"name": args.name[:100]},
    )
    print(f"Created thread '{data['name']}' (id: {data['id']})")


def cmd_list_threads(args: argparse.Namespace) -> None:
    channel = request("GET", f"/channels/{args.channel_id}")
    gid = channel.get("guild_id")
    if not gid:
        sys.exit("Cannot list threads for this channel type.")
    data = request("GET", f"/guilds/{gid}/threads/active")
    threads = [
        t for t in data.get("threads", []) if t.get("parent_id") == args.channel_id
    ]
    if not threads:
        print("No active threads.")
        return
    for t in threads:
        print(f"- {t['name']}  (id: {t['id']})")


def cmd_search_messages(args: argparse.Namespace) -> None:
    limit = max(1, min(100, args.limit))
    msgs = request(
        "GET",
        f"/channels/{args.channel_id}/messages",
        params={"limit": limit},
    )
    q = args.query.lower()
    matches = [m for m in msgs if q in (m.get("content") or "").lower()]
    if not matches:
        print(f"No messages matching '{args.query}' in last {limit} messages.")
        return
    for msg in reversed(matches):
        print(f"[{msg['id']}] {msg['author']['username']}: {msg['content']}")


def cmd_send_embed(args: argparse.Namespace) -> None:
    embed: dict[str, Any] = {
        "title": args.title,
        "description": args.description,
        "color": args.color,
    }
    if args.url:
        embed["url"] = args.url
    data = request(
        "POST",
        f"/channels/{args.channel_id}/messages",
        body={"embeds": [embed]},
    )
    print(f"Sent embed message {data['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="discord.py", description="Discord bot CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-guilds", help="List servers the bot has joined.")

    p = sub.add_parser("list-channels", help="List text channels in a guild.")
    p.add_argument("--guild-id", help="Guild ID (default: DISCORD_GUILD_ID).")

    p = sub.add_parser("get-channel-info", help="Get details for a channel.")
    p.add_argument("channel_id")

    p = sub.add_parser("send-message", help="Send a text message.")
    p.add_argument("channel_id")
    p.add_argument("content")

    p = sub.add_parser("read-messages", help="Read recent messages.")
    p.add_argument("channel_id")
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("reply", help="Reply to a specific message.")
    p.add_argument("channel_id")
    p.add_argument("message_id")
    p.add_argument("content")

    p = sub.add_parser("edit-message", help="Edit a bot-authored message.")
    p.add_argument("channel_id")
    p.add_argument("message_id")
    p.add_argument("content")

    p = sub.add_parser("delete-message", help="Delete a message.")
    p.add_argument("channel_id")
    p.add_argument("message_id")

    p = sub.add_parser("add-reaction", help="Add a reaction to a message.")
    p.add_argument("channel_id")
    p.add_argument("message_id")
    p.add_argument("emoji", help="Unicode emoji or custom format name:id.")

    p = sub.add_parser("create-thread", help="Create a thread from a message.")
    p.add_argument("channel_id")
    p.add_argument("message_id")
    p.add_argument("name")

    p = sub.add_parser("list-threads", help="List active threads in a channel.")
    p.add_argument("channel_id")

    p = sub.add_parser("search-messages", help="Search recent messages locally.")
    p.add_argument("channel_id")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=25)

    p = sub.add_parser("send-embed", help="Send a rich embed message.")
    p.add_argument("channel_id")
    p.add_argument("title")
    p.add_argument("description")
    p.add_argument("--color", type=int, default=0x5865F2)
    p.add_argument("--url", default="")

    args = parser.parse_args()
    dispatch = {
        "list-guilds": cmd_list_guilds,
        "list-channels": cmd_list_channels,
        "get-channel-info": cmd_get_channel_info,
        "send-message": cmd_send_message,
        "read-messages": cmd_read_messages,
        "reply": cmd_reply,
        "edit-message": cmd_edit_message,
        "delete-message": cmd_delete_message,
        "add-reaction": cmd_add_reaction,
        "create-thread": cmd_create_thread,
        "list-threads": cmd_list_threads,
        "search-messages": cmd_search_messages,
        "send-embed": cmd_send_embed,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
