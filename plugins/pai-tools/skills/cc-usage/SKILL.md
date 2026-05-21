---
name: cc-usage
description: Use when reporting Claude Code spend and token usage from local session logs (~/.claude/projects/**/*.jsonl). Aggregates by day or month, breaks down by model, applies tiered LiteLLM pricing. No API key required — reads files Claude Code already writes.
---

# CC Usage

Read your own Claude Code session logs and report cost + token usage. Stdlib-only Python — fetches pricing from LiteLLM on first run.

## When to use

- "How much have I spent on Claude Code this month?"
- "Daily cost breakdown for the last 7 days."
- "Lifetime total spend across all sessions."
- Comparing model mix — Opus vs. Sonnet vs. Haiku share of spend.

## When NOT to use

- You want billing source-of-truth — go to your Anthropic account dashboard. This skill estimates from session logs and may differ slightly from billing (especially for Pro/Max subscriptions and edge cases).
- You want per-conversation deep-dives — this aggregates, doesn't drill into individual sessions.
- The machine isn't your dev box — Claude Code only writes logs to `~/.claude/projects/` on the machine you actually used.

## Setup

None. Reads `~/.claude/projects/**/*.jsonl` directly. Pricing data is pulled from LiteLLM's pinned JSON on each fresh process (cached in-memory per invocation).

If you've moved your Claude Code state directory:

```bash
export CLAUDE_CONFIG_DIR="$HOME/.claude-elsewhere"
```

## Invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/cc-usage/scripts/cc_usage.py" daily --days 7
python3 "${CLAUDE_PLUGIN_ROOT}/skills/cc-usage/scripts/cc_usage.py" monthly --days 90
python3 "${CLAUDE_PLUGIN_ROOT}/skills/cc-usage/scripts/cc_usage.py" total           # all-time
python3 "${CLAUDE_PLUGIN_ROOT}/skills/cc-usage/scripts/cc_usage.py" total --days 30
```

## Subcommands

- `daily [--days 30]` — daily breakdown with per-model rows and per-day totals.
- `monthly [--days 30]` — monthly buckets.
- `total [--days N]` — single overall total. Omit `--days` for lifetime.

## How costs are computed

- Pricing source: <https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json> (the same source ccusage uses).
- Model resolution: exact match, then `anthropic/<model>`, then substring match.
- Tiered pricing: tokens above 200k use the `*_above_200k_tokens` rate when present.
- Cache tokens use `cache_creation_input_token_cost` / `cache_read_input_token_cost`.
- Fast mode (Opus): when `usage.speed === "fast"`, cost is multiplied by `provider_specific_entry.fast` from the pricing entry (often `6.0` for Opus fast).

## Rules

- **Estimates only.** Numbers are derived from local logs and the public LiteLLM pricing snapshot. Treat them as ballpark, not invoice.
- **The numbers themselves are sensitive** — they reveal usage patterns and spend. Don't paste raw output into public content. Pair with `auditing-for-confidential-data`.
- **Per-machine.** A laptop's `~/.claude/projects/` doesn't contain sessions you ran on another machine. To get a full picture, run on each machine you use.
- **First call fetches pricing from GitHub.** Offline runs will fail at that step. Subsequent calls within the same process reuse the in-memory cache.
