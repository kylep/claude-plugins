# kytrade

Skills for operating [kytrade](https://github.com/kylep/multi/tree/main/apps/kytrade),
Kyle's personal trading toolkit — a Postgres-backed price database with
twin Typer CLI (`kt`) and FastAPI interfaces. The toolkit is developed
prompt-first: its `PROMPTS.md` lists the prompts these skills serve.

## Skills

- **operating-kytrade**: bootstrap from scratch (including `.env`
  secret generation), health/staleness checks, incremental price
  pulls, S&P 500 membership reconciliation, cost/safety rails
  (~503-request refreshes, `--full` re-downloads, never the k8s DB)
- **analyzing-market-data**: answer market questions from stored
  data — window performance, multi-symbol comparisons, gainers/losers,
  sector performance, 52-week high/low screening, volatility — with
  composition patterns and honesty rules (report only computed
  numbers, state data freshness)

## Requirements

The kylep/multi repo checked out with `apps/kytrade/` present, uv,
and Docker for the local postgres. The skills run everything through
`uv run kt ... --json`.
