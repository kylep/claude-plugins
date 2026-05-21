#!/usr/bin/env python3
"""OpenRouter CLI: check API key usage and look up model pricing.

Ported from a TypeScript MCP server (apps/mcp-servers/openrouter/src/index.ts).
Requires OPENROUTER_API_KEY in the environment.

Usage:
  openrouter.py get-usage
  openrouter.py get-model-pricing [--model SEARCH_TERM]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API_BASE = "https://openrouter.ai/api/v1"


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY environment variable is not set")
    return key


def api_fetch(path: str) -> Any:
    req = Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {get_api_key()}"},
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        sys.exit(f"OpenRouter API error {e.code}: {body}")


def format_dollars(credits: float) -> str:
    return f"${credits:.4f}"


def per_million_tokens(per_token: str | float) -> str:
    try:
        n = float(per_token)
    except (TypeError, ValueError):
        return "free"
    if n == 0:
        return "free"
    return f"${n * 1_000_000:.2f}"


def cmd_get_usage(_args: argparse.Namespace) -> None:
    data = api_fetch("/key")
    k = data["data"]

    lines = [
        f"Key: {k.get('label') or '(unnamed)'}",
        f"Free tier: {'yes' if k.get('is_free_tier') else 'no'}",
        "",
        "Usage:",
        f"  Today:  {format_dollars(k.get('usage_daily', 0))}",
        f"  Week:   {format_dollars(k.get('usage_weekly', 0))}",
        f"  Month:  {format_dollars(k.get('usage_monthly', 0))}",
        f"  Total:  {format_dollars(k.get('usage', 0))}",
    ]

    if k.get("limit") is not None and k.get("limit_remaining") is not None:
        lines.extend(
            [
                "",
                "Credit limit:",
                f"  Limit:     {format_dollars(k['limit'])}",
                f"  Remaining: {format_dollars(k['limit_remaining'])}",
            ]
        )

    print("\n".join(lines))


def cmd_get_model_pricing(args: argparse.Namespace) -> None:
    data = api_fetch("/models")
    models = data["data"]

    if args.model:
        term = args.model.lower()
        models = [
            m
            for m in models
            if term in m["id"].lower() or term in m["name"].lower()
        ]

    if not models:
        print(f'No models found matching "{args.model}"')
        return

    cap = 20
    shown = models[:cap]
    truncated = len(models) > cap

    blocks = []
    for m in shown:
        prompt = per_million_tokens(m["pricing"]["prompt"])
        completion = per_million_tokens(m["pricing"]["completion"])
        ctx_k = m["context_length"] / 1000
        blocks.append(
            f"{m['id']}\n"
            f"  Prompt: {prompt}/M tokens  "
            f"Completion: {completion}/M tokens  "
            f"Context: {ctx_k:.0f}k"
        )

    output = "\n\n".join(blocks)
    if truncated:
        output += (
            f"\n\n... and {len(models) - cap} more. "
            "Use a search term to narrow results."
        )
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="openrouter.py",
        description="OpenRouter CLI — usage and model pricing.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "get-usage", help="Show API key usage and credit balance."
    )

    pricing = subparsers.add_parser(
        "get-model-pricing",
        help="Look up model pricing (optionally filter by search term).",
    )
    pricing.add_argument(
        "--model", help="Model ID or search term to filter results."
    )

    args = parser.parse_args()

    if args.command == "get-usage":
        cmd_get_usage(args)
    elif args.command == "get-model-pricing":
        cmd_get_model_pricing(args)


if __name__ == "__main__":
    main()
