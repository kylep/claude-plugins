---
name: openrouter-usage
description: Use when the user asks about OpenRouter API spend, credit balance, daily/weekly/monthly usage, or wants to look up the per-million-token pricing of an OpenRouter model. Requires OPENROUTER_API_KEY in the environment.
---

# OpenRouter Usage

Query OpenRouter's API for key usage and model pricing.

## When to use

- "How much have I spent on OpenRouter this month?"
- "What's my credit balance?"
- "How much does claude-sonnet-4-6 cost on OpenRouter?"
- "Find me cheap free-tier models on OpenRouter."

## When NOT to use

- The user wants pricing from a different provider (Anthropic direct, OpenAI). This is OpenRouter-specific.
- The user wants to call a model through OpenRouter — use the OpenAI-compatible API directly with the OpenRouter base URL; this skill is read-only.

## Setup (one time)

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

The script reads the key from the environment on every call. Put it in the shell rc file you actually use.

## Invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/openrouter-usage/scripts/openrouter.py" get-usage
python3 "${CLAUDE_PLUGIN_ROOT}/skills/openrouter-usage/scripts/openrouter.py" get-model-pricing --model claude
```

If `$CLAUDE_PLUGIN_ROOT` isn't set (you're running outside Claude Code), substitute the plugin's install path.

### Subcommands

| Subcommand | What it does |
|---|---|
| `get-usage` | Prints key label, free-tier flag, daily/weekly/monthly/total spend, and credit limit (if set). |
| `get-model-pricing [--model TERM]` | Lists OpenRouter models with prompt + completion price per million tokens and context length. With `--model`, filters by model ID or name (case-insensitive substring). Caps output at 20 models. |

## Output format

Plain text. Both subcommands print human-readable summaries, not JSON. Pipe through `jq` or process the text directly.

## Why a script, not an MCP server

The original was a TypeScript MCP server. As a Python CLI it's stdlib-only (`urllib.request`, `json`, `argparse`), runs without `npm install`, and works in any shell — no MCP host required. Cost is the loss of native MCP integration; benefit is portability and zero install footprint.

## Rules

- **Never embed the API key in the command line.** Always use the environment variable. The script reads `OPENROUTER_API_KEY`; do not pass it as a flag.
- **Don't print the API key in responses.** The script doesn't, but if the user asks "what's my key set to," don't read and echo it. Confirm presence (`is set` vs `not set`) without revealing the value.
