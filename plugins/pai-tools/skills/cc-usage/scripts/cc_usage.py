#!/usr/bin/env python3
"""Claude Code usage and cost CLI.

Ported from a TypeScript MCP server (apps/mcp-servers/cc-usage/src/index.ts).
Reads ~/.claude/projects/**/*.jsonl, parses session usage records, fetches
LiteLLM model pricing, and aggregates spend by day or month.

Uses local session logs only — there is no Anthropic billing API for this.
Cost estimates use the same pricing source as ccusage (BerriAI/litellm).

Env vars:
  CLAUDE_CONFIG_DIR  — override ~/.claude (default: $HOME/.claude)

Usage:
  cc_usage.py daily   [--days 30]
  cc_usage.py monthly [--days 30]
  cc_usage.py total   [--days N]    (omit --days for all-time)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

LITELLM_PRICING_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
TIER_THRESHOLD = 200_000


def projects_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(env) if env else Path.home() / ".claude"
    return base / "projects"


def find_jsonl_files(base: Path) -> list[Path]:
    if not base.is_dir():
        return []
    return list(base.rglob("*.jsonl"))


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = record.get("message") or {}
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                if not isinstance(usage.get("input_tokens"), int):
                    continue
                entries.append(
                    {
                        "timestamp": record.get("timestamp", "") or "",
                        "model": message.get("model")
                        or record.get("model")
                        or "unknown",
                        "input_tokens": usage["input_tokens"],
                        "output_tokens": usage.get("output_tokens", 0) or 0,
                        "cache_creation_input_tokens": usage.get(
                            "cache_creation_input_tokens"
                        )
                        or 0,
                        "cache_read_input_tokens": usage.get(
                            "cache_read_input_tokens"
                        )
                        or 0,
                        "speed": usage.get("speed"),
                        "costUSD": record.get("costUSD"),
                    }
                )
    except OSError:
        pass
    return entries


_pricing_cache: dict[str, dict[str, Any]] | None = None


def get_pricing() -> dict[str, dict[str, Any]]:
    global _pricing_cache
    if _pricing_cache is not None:
        return _pricing_cache
    try:
        with urlopen(LITELLM_PRICING_URL, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        sys.exit(f"Failed to fetch LiteLLM pricing: {e}")
    pricing = {k: v for k, v in raw.items() if isinstance(v, dict)}
    _pricing_cache = pricing
    return pricing


def find_model_pricing(
    pricing: dict[str, dict[str, Any]], model: str
) -> dict[str, Any] | None:
    if model in pricing:
        return pricing[model]
    prefixed = f"anthropic/{model}"
    if prefixed in pricing:
        return pricing[prefixed]
    for key in pricing:
        unprefixed = key.replace("anthropic/", "")
        if model in key or unprefixed in model:
            return pricing[key]
    return None


def tiered_cost(
    tokens: int, base_rate: float | None, tiered_rate: float | None
) -> float:
    if not base_rate:
        return 0.0
    if tokens > TIER_THRESHOLD and tiered_rate:
        return TIER_THRESHOLD * base_rate + (tokens - TIER_THRESHOLD) * tiered_rate
    return tokens * base_rate


def calc_cost(entry: dict[str, Any], mp: dict[str, Any]) -> float:
    cost = (
        tiered_cost(
            entry["input_tokens"],
            mp.get("input_cost_per_token"),
            mp.get("input_cost_per_token_above_200k_tokens"),
        )
        + tiered_cost(
            entry["output_tokens"],
            mp.get("output_cost_per_token"),
            mp.get("output_cost_per_token_above_200k_tokens"),
        )
        + tiered_cost(
            entry["cache_creation_input_tokens"],
            mp.get("cache_creation_input_token_cost"),
            mp.get("cache_creation_input_token_cost_above_200k_tokens"),
        )
        + tiered_cost(
            entry["cache_read_input_tokens"],
            mp.get("cache_read_input_token_cost"),
            mp.get("cache_read_input_token_cost_above_200k_tokens"),
        )
    )
    speed = entry.get("speed")
    fast_mult = (mp.get("provider_specific_entry") or {}).get("fast")
    if speed == "fast" and fast_mult:
        cost *= fast_mult
    return cost


def format_dollars(n: float) -> str:
    return f"${n:.4f}"


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def load_all_entries() -> list[dict[str, Any]]:
    base = projects_dir()
    entries: list[dict[str, Any]] = []
    for f in find_jsonl_files(base):
        entries.extend(parse_jsonl(f))
    return entries


def aggregate(entries: list[dict[str, Any]], key_fn) -> dict[str, dict[str, Any]]:
    pricing = get_pricing()
    groups: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = key_fn(entry["timestamp"])
        summary = groups.setdefault(
            key,
            {
                "date": key,
                "inputTokens": 0,
                "outputTokens": 0,
                "cacheCreationTokens": 0,
                "cacheReadTokens": 0,
                "totalCost": 0.0,
                "models": {},
            },
        )
        mp = find_model_pricing(pricing, entry["model"])
        cost = calc_cost(entry, mp) if mp else (entry.get("costUSD") or 0.0)
        summary["inputTokens"] += entry["input_tokens"]
        summary["outputTokens"] += entry["output_tokens"]
        summary["cacheCreationTokens"] += entry["cache_creation_input_tokens"]
        summary["cacheReadTokens"] += entry["cache_read_input_tokens"]
        summary["totalCost"] += cost
        m = summary["models"].setdefault(
            entry["model"], {"inputTokens": 0, "outputTokens": 0, "cost": 0.0}
        )
        m["inputTokens"] += entry["input_tokens"]
        m["outputTokens"] += entry["output_tokens"]
        m["cost"] += cost
    return groups


def to_date(iso: str) -> str:
    return iso[:10] if iso else "unknown"


def to_month(iso: str) -> str:
    return iso[:7] if iso else "unknown"


def filter_by_days(
    entries: list[dict[str, Any]], days: int | None
) -> list[dict[str, Any]]:
    if days is None:
        return entries
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat()
    return [e for e in entries if e["timestamp"] >= cutoff]


def print_summaries(summaries: dict[str, dict[str, Any]], title: str) -> None:
    if not summaries:
        print("No usage data found.")
        return
    print(title)
    print()
    total_cost = 0.0
    total_in = 0
    total_out = 0
    for key in sorted(summaries):
        s = summaries[key]
        total_cost += s["totalCost"]
        total_in += s["inputTokens"]
        total_out += s["outputTokens"]
        print(
            f"{s['date']}  {format_dollars(s['totalCost'])}  "
            f"in: {format_tokens(s['inputTokens'])}  "
            f"out: {format_tokens(s['outputTokens'])}"
        )
        for model, m in sorted(
            s["models"].items(), key=lambda kv: kv[1]["cost"], reverse=True
        ):
            print(
                f"  {model}: {format_dollars(m['cost'])}  "
                f"in: {format_tokens(m['inputTokens'])}  "
                f"out: {format_tokens(m['outputTokens'])}"
            )
    print()
    print(
        f"Total: {format_dollars(total_cost)}  "
        f"in: {format_tokens(total_in)}  out: {format_tokens(total_out)}"
    )


def cmd_daily(args: argparse.Namespace) -> None:
    entries = filter_by_days(load_all_entries(), args.days)
    summaries = aggregate(entries, to_date)
    print_summaries(
        summaries, f"Daily Claude Code usage (last {args.days} days)"
    )


def cmd_monthly(args: argparse.Namespace) -> None:
    entries = filter_by_days(load_all_entries(), args.days)
    summaries = aggregate(entries, to_month)
    print_summaries(
        summaries, f"Monthly Claude Code usage (last {args.days} days)"
    )


def cmd_total(args: argparse.Namespace) -> None:
    entries = filter_by_days(load_all_entries(), args.days)
    pricing = get_pricing()
    total_cost = 0.0
    total_in = 0
    total_out = 0
    model_costs: dict[str, float] = {}
    for entry in entries:
        mp = find_model_pricing(pricing, entry["model"])
        cost = calc_cost(entry, mp) if mp else (entry.get("costUSD") or 0.0)
        total_cost += cost
        total_in += entry["input_tokens"]
        total_out += entry["output_tokens"]
        model_costs[entry["model"]] = model_costs.get(entry["model"], 0.0) + cost

    period = f"last {args.days} days" if args.days else "all time"
    print(f"Claude Code usage ({period})")
    print()
    print(f"Total cost: {format_dollars(total_cost)}")
    print(f"Input tokens: {format_tokens(total_in)}")
    print(f"Output tokens: {format_tokens(total_out)}")
    print()
    print("By model:")
    for model, cost in sorted(model_costs.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {model}: {format_dollars(cost)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cc_usage.py",
        description="Claude Code usage and cost estimates from local session logs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("daily", help="Daily breakdown.")
    p.add_argument("--days", type=int, default=30)

    p = sub.add_parser("monthly", help="Monthly breakdown.")
    p.add_argument("--days", type=int, default=30)

    p = sub.add_parser("total", help="Lifetime or N-day total.")
    p.add_argument("--days", type=int, default=None)

    args = parser.parse_args()
    {
        "daily": cmd_daily,
        "monthly": cmd_monthly,
        "total": cmd_total,
    }[args.command](args)


if __name__ == "__main__":
    main()
