#!/usr/bin/env python3
"""Google News (gnews.io) CLI: search articles and fetch top headlines.

Ported from a TypeScript MCP server (apps/mcp-servers/google-news/src/index.ts).
Requires GNEWS_API_KEY in the environment. Sign up at https://gnews.io.

Output is wrapped in <news-data> tags and headline/description/content fields
are sanitized for common prompt-injection patterns, since news APIs return
untrusted external text.

Usage:
  google_news.py search "AI agents" [--max 10] [--lang en] [--from ISO] [--to ISO]
  google_news.py headlines [--category technology] [--max 10] [--lang en]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

API_BASE = "https://gnews.io/api/v4"
MAX_CONTENT_LENGTH = 500

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"^system\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^assistant\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^user\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"disregard\s+(all\s+)?(prior|above|previous)", re.IGNORECASE),
    re.compile(
        r"do\s+not\s+follow\s+(your|the)\s+(original|previous)", re.IGNORECASE
    ),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"override\s+(your|all)\s+(rules|instructions)", re.IGNORECASE),
]

CATEGORIES = [
    "general",
    "world",
    "nation",
    "business",
    "technology",
    "entertainment",
    "sports",
    "science",
    "health",
]


def get_api_key() -> str:
    key = os.environ.get("GNEWS_API_KEY")
    if not key:
        sys.exit("GNEWS_API_KEY environment variable is not set")
    return key


def sanitize(text: str) -> str:
    cleaned = text or ""
    for pattern in INJECTION_PATTERNS:
        cleaned = pattern.sub("[removed]", cleaned)
    return cleaned


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def api_fetch(endpoint: str, params: dict[str, str]) -> dict[str, Any]:
    qs = urlencode({**params, "apikey": get_api_key()})
    url = f"{API_BASE}/{endpoint}?{qs}"
    try:
        with urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        sys.exit(f"GNews API error {e.code}: {body}")


def format_articles(articles: list[dict[str, Any]]) -> str:
    if not articles:
        return "No articles found."
    blocks: list[str] = []
    for i, a in enumerate(articles, start=1):
        published_at = a.get("publishedAt", "")
        date = published_at[:16] if published_at else ""
        title = sanitize(a.get("title", ""))
        desc = sanitize(a.get("description") or "(no description)")
        source = sanitize(a.get("source", {}).get("name", ""))
        url = sanitize(a.get("url", ""))

        lines = [f"{i}. **{title}**", f"   {desc}"]
        content = a.get("content")
        if content and content != a.get("description"):
            lines.append(f"   {truncate(sanitize(content), MAX_CONTENT_LENGTH)}")
        lines.append(f"   Source: {source} | {date}")
        lines.append(f"   {url}")
        blocks.append("\n".join(lines))

    return (
        '<news-data source="gnews-api">\n'
        + "\n\n".join(blocks)
        + "\n</news-data>"
    )


def cmd_search(args: argparse.Namespace) -> None:
    params: dict[str, str] = {
        "q": args.query,
        "max": str(args.max),
        "lang": args.lang,
    }
    if args.from_:
        params["from"] = args.from_
    if args.to:
        params["to"] = args.to

    data = api_fetch("search", params)
    header = f"Found {data.get('totalArticles', 0)} articles for \"{args.query}\":\n"
    print(header + format_articles(data.get("articles", [])))


def cmd_headlines(args: argparse.Namespace) -> None:
    params: dict[str, str] = {
        "category": args.category,
        "max": str(args.max),
        "lang": args.lang,
    }
    data = api_fetch("top-headlines", params)
    header = f"Top {args.category} headlines:\n"
    print(header + format_articles(data.get("articles", [])))


def add_max(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--max",
        type=int,
        default=10,
        choices=range(1, 11),
        metavar="N",
        help="Max articles to return (1-10, default 10).",
    )


def add_lang(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--lang", default="en", help="Language code (default 'en')."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="google_news.py",
        description="Search Google News (gnews.io) and fetch top headlines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search articles by keyword.")
    search.add_argument("query", help='Search query (e.g. "AI agents").')
    add_max(search)
    add_lang(search)
    search.add_argument(
        "--from",
        dest="from_",
        help="Oldest article date in ISO 8601 (e.g. 2026-03-14T00:00:00Z).",
    )
    search.add_argument("--to", help="Newest article date in ISO 8601.")

    headlines = subparsers.add_parser(
        "headlines", help="Get top headlines, optionally filtered by category."
    )
    headlines.add_argument(
        "--category",
        choices=CATEGORIES,
        default="technology",
        help="News category (default 'technology').",
    )
    add_max(headlines)
    add_lang(headlines)

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "headlines":
        cmd_headlines(args)


if __name__ == "__main__":
    main()
