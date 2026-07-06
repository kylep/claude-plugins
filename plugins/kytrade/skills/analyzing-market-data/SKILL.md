---
name: analyzing-market-data
description: Use when asked market questions answerable from kytrade's stored price data — how a stock performed, comparisons between tickers, biggest gainers/losers, sector performance, stocks near 52-week highs/lows, or volatility.
---

# Analyzing market data with kytrade

Answer market questions from Kyle's own price database (Postgres
document store, daily OHLCV back to each listing's start, auto-adjusted
closes rounded to 4 decimals). Universe: S&P 500 (USD) + S&P/TSX 60
(CAD, `.TO` tickers) + tracked ETFs (SPY, QQQ, XIU.TO). Returns are
percentages, so cross-currency comparisons stay meaningful; flag the
currency if absolute prices are quoted. Run from `apps/kytrade/` with
`uv run kt ... --json`.

## Recipes

| Question shape | Command |
|----------------|---------|
| "How has X performed over N days?" | `kt analyze performance X --days N --json` |
| "Compare X, Y, Z since ..." | `kt analyze compare X Y Z --days N --json` |
| "Biggest gainers/losers this month" | `kt analyze movers --days 30 --top 10 --json` |
| "Best/worst sector this quarter" | `kt analyze sectors --days 90 --json` |
| "Stocks near their 52-week high/low" | `kt analyze near-extreme --kind high --threshold-pct 5 --json` |
| "How volatile was X?" | `kt analyze volatility X --window-days 21 --json` |

All windows are calendar days measured back from the symbol's most
recent stored trading day. Returns are percentages over the window
(`return_pct`), computed close-to-close.

## Before answering

1. `uv run kt status --json` — if staleness shows the relevant symbols
   weren't pulled today, say so in the answer or `kt refresh` first
   (refresh = ~565 network calls; for one or two symbols prefer
   `kt data pull -s X`).
2. A `NotEnoughData` error (exit 1) means the symbol has no/too-little
   stored history — pull it, don't guess.

## Composition

The commands compose for questions no single command answers: filter
`near-extreme` hits by sector membership (`kt db get stock/sectors`),
rank a sector's members by running `compare` on its ticker list, or
answer "calmest Energy stock near its low" with `near-extreme` +
`volatility` per hit. Do the joining/math yourself from the JSON.

## Honesty rules (non-negotiable)

- Report only numbers that came out of these commands. Never estimate,
  extrapolate, or fill gaps from memory — training-data prices are
  stale and this database is the source of truth.
- State the data's freshness when it matters (the `end_date` field
  says what day a window actually ended on).
- If the data can't answer the question, say exactly that and what a
  pull would fix.
