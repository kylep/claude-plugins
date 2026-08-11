# pai-tools test suites

Three pytest suites cover the scripts under `plugins/pai-tools/skills/*/scripts/`.
Markdown (`SKILL.md`, READMEs) is documentation and is not tested.

| Suite | Marker | Network | API keys | What it proves |
|---|---|---|---|---|
| unit | `unit` | none | none | pure logic (formatting, parsing, precedence, boundaries) |
| integration | `integration` | mocked (`urlopen` / `subprocess`) | none | every subcommand builds the right request and renders the right output, including error paths |
| contract | `contract` | **live** | **real** | the live API still returns the fields each script depends on |

## Running

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

.venv/bin/python -m pytest                      # unit + integration (contract deselected by default)
.venv/bin/python -m pytest -m unit
.venv/bin/python -m pytest -m integration
.venv/bin/python -m pytest -m contract          # opt-in; needs real keys (see below)
```

A bare `pytest` never touches a live API: `pytest.ini` sets
`addopts = -m "not contract"`. The contract suite runs only when you ask for it
with `-m contract`, and each test auto-skips unless its credentials are present.

## Coverage matrix

| Script | Subcommands | unit | integration | contract |
|---|---|:--:|:--:|:--:|
| `openrouter.py` | get-usage, get-model-pricing | ✓ | ✓ | ✓ (read-only) |
| `linear.py` | list/get/create/update-issue, add/list-comments, list-teams/projects | ✓ | ✓ | ✓ (read + create/cleanup) |
| `strava.py` | athlete(-zones/-stats/-clubs/-routes), activities, activity(-comments/-kudos/-laps/-zones/-streams), club(-activities/-members/-admins), gear, route(-export/-streams), segment(s-starred/-explore/-streams), segment-effort(s/-streams), upload | ✓ | ✓ | ✓ (read-only, auto-skip) |
| `discord.py` | list-guilds/channels, get-channel-info, send/read/reply/edit/delete-message, add-reaction, create/list-threads, search-messages, send-embed | ✓ | ✓ | ✓ (read + send/delete) |
| `google_news.py` | search, headlines | ✓ | ✓ | ✓ (read-only) |
| `ga4.py` | run-report, realtime | ✓ | ✓ | ✓ (read-only, auto-skip) |
| `gsc.py` | search-analytics, inspect-url, list-sitemaps, submit-sitemap | ✓ | ✓ | ✓ (read-only, auto-skip) |
| `openobserve.py` | search-logs, error-summary, recent-errors, list-streams, stream-schema, list-alerts, get-alert | ✓ | ✓ | ✓ (read-only) |
| `cc_usage.py` | daily, monthly, total | ✓ | ✓ | — (no API; reads local files) |
| `bitwarden.py` | status, sync, list/get/create/edit/delete-item, generate-password, list-folders | ✓ | ✓ | ✓ (read-only) |
| `desktop.py` | take, click, double-click, type | ✓ | ✓ | — (no API; local side effects) |

`cc_usage.py` and `desktop.py` have no remote API, so they have no contract suite;
they are fully covered by unit + integration (temp config dirs / mocked subprocess).

## Environment variables for the contract suite

Each contract test skips unless its variables are set. Read-only tests need only
the script's normal auth; the two **mutating** tests need an extra disposable
target so writes never land on a real resource.

| Script | Required for read-only contract | Extra for mutating contract |
|---|---|---|
| `openrouter.py` | `OPENROUTER_API_KEY` | — |
| `google_news.py` | `GNEWS_API_KEY` | — |
| `linear.py` | `LINEAR_API_KEY` | `LINEAR_TEST_TEAM` (a disposable team name/key) |
| `strava.py` | `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN` | — (read-only) |
| `discord.py` | `DISCORD_BOT_TOKEN` (+ `DISCORD_GUILD_ID` for list-channels) | `DISCORD_TEST_CHANNEL_ID` (a throwaway channel) |
| `openobserve.py` | `O2_URL`, `O2_TOKEN`, `O2_ORG` | — |
| `ga4.py` | `GA4_PROPERTY_ID`, `GOOGLE_APPLICATION_CREDENTIALS` + `google-analytics-data` installed | — |
| `gsc.py` | `GSC_SITE_URL` + OAuth `token.json` + `google-api-python-client` installed | — |
| `bitwarden.py` | `BW_SESSION` + the `bw` CLI on `PATH` | — |

### Mutating contract tests (create → assert → clean up)

- **Linear**: `LINEAR_TEST_TEAM` set → creates an issue via the CLI, asserts it,
  then deletes it via a direct GraphQL `issueDelete` in a `finally` block.
- **Discord**: `DISCORD_TEST_CHANNEL_ID` set → sends a message via the CLI,
  asserts it, then deletes it via the CLI `delete-message` in a `finally` block.

Cleanup runs even if assertions fail. Point these at disposable resources only.

## CI

`.github/workflows/tests.yml` installs `requirements-dev.txt` and runs
`pytest -m "unit or integration"` on push and PR. The contract suite is never
run in CI — it needs real keys and makes live calls.

## Notes on the harness

- `tests/conftest.py` holds the shared helpers: `load_script` (imports a script
  by path), `patch_urlopen` / `FakeUrlopen` / `FakeResponse` (HTTP mocking with
  request capture), `http_error`, `run_cli`, and `requires_env`.
- The google libraries that `ga4.py`/`gsc.py` use are imported lazily inside
  their functions, so integration mocks them via `sys.modules` injection and the
  libraries are **not** required for unit/integration or CI. Install them only to
  run the ga4/gsc contract tests live.
