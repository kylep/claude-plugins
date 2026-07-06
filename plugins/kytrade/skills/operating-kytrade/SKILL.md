---
name: operating-kytrade
description: Use when asked to set up, health-check, refresh, or pull data into kytrade (Kyle's trading toolkit) — bootstrap from scratch, manage the postgres container and .env secrets, pull stock price history, or reconcile S&P 500 membership.
---

# Operating kytrade

Kytrade lives at `apps/kytrade/` in kylep/multi. The `kt` CLI and the
FastAPI ingress are thin twins over one function layer — anything here
also works over HTTP (`bin/start-api.sh`, spec in `openapi.json`).

## Ground rules

- Run everything from `apps/kytrade/` via `uv run kt ...` — never bare
  `python`, `pip`, or `poetry`.
- Machine-readable output: pass `--json` on any read command.
- Local docker-compose postgres only. NEVER point at the k8s database.
- Secrets: `POSTGRES_PASSWORD` comes from the environment or a
  git-ignored `.env` (mode 600). `kt bootstrap` generates one if
  missing. Never print the password, commit it, or write it anywhere
  besides `.env`. If Kyle wants it stored durably, suggest Bitwarden
  (`bw`) — don't do it unasked.

## Is it up?

```bash
uv run kt status --json
```

- `db_ok: false` → `docker compose up -d postgres --wait` (needs
  POSTGRES_PASSWORD available; see bootstrap) and retry
- `tables_ok: false` → run bootstrap
- `staleness` shows counts by last-pull age: today / week / older / never

## Bootstrap from scratch

```bash
docker compose up -d postgres --wait   # after ensuring .env exists, or:
uv run kt bootstrap --json             # generates .env if needed
docker compose up -d postgres --wait   # now compose can read .env
uv run kt bootstrap --json             # idempotent: tables + S&P 500 membership
uv run kt refresh --json               # pull all price history (~503 symbols, minutes)
```

Bootstrap loads membership live from Wikipedia and falls back to the
bundled Oct 2022 snapshot when offline. It never pulls prices — that's
`kt refresh`.

## Day-to-day data operations

```bash
uv run kt refresh --json                  # staleness-aware pull of every symbol
uv run kt data pull -s AAPL --json        # one symbol, incremental
uv run kt data pull -s AAPL --full        # re-download (adjusted-price drift)
uv run kt data prices AAPL --tail 30 --json
uv run kt data symbols --json             # ticker → metadata
uv run kt data load-sp500 --json          # reconcile membership, returns joins/leaves
uv run kt data membership-log --json      # dated joins/leaves from past loads
```

Pulling is incremental and skips symbols already pulled today — a
second pull returning 0 new days is correct behavior, not a bug.

## Cost and safety awareness

- `kt refresh`, `kt data pull --all`, `kt data backfill-sp500` make
  ~503 Yahoo Finance requests: minutes of wall time, rate-limit
  sensitive. Don't run them casually or in loops.
- `--full` re-downloads everything. Warranted occasionally because
  auto-adjusted history drifts after splits/dividends; not per-pull.
- `kt db set` replaces a document wholesale — `kt db get` first.
- `rm -rf` is hook-blocked in this repo; use `rm -r`
  (e.g. `bin/reset-database.sh` wipes the postgres volume).

## Troubleshooting

- Wikipedia 403 on load-sp500: fetches use a real User-Agent; if it
  still fails, `--file raw-data/indexes/spy-oct17-2022.xlsx`.
- Yahoo returning empty history: check the ticker uses dashes for
  class shares (`BRK-B`, not `BRK.B`).
- Tests: `uv run pytest` (unit, no DB); `bin/integration-test.sh`
  (real postgres). Both must pass before committing changes.
