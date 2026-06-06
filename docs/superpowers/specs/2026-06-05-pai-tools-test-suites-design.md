# pai-tools test suites — design

**Date:** 2026-06-05
**Status:** Approved (design phase)

## Goal

Add three test suites for the `pai-tools` plugin scripts that together exercise
the full toolset and verify each script does what its docs claim:

1. **unit** — pure logic, no network, no keys
2. **integration** — every subcommand end-to-end with mocked HTTP/subprocess, no keys
3. **contract** — real API keys against live services, exercising the API-call scripts

Markdown (`SKILL.md`, READMEs) is out of scope — it is documentation, not tested.

## Scope: the scripts under test

All ten scripts live under `plugins/pai-tools/skills/*/scripts/`.

| Script | Auth | Reaches | Mutates | Notes |
|---|---|---|---|---|
| `openrouter.py` | `OPENROUTER_API_KEY` | OpenRouter REST | no | stdlib `urllib` |
| `linear.py` | `LINEAR_API_KEY` | Linear GraphQL | yes (create/update/comment) | stdlib `urllib`; no delete command |
| `discord.py` | `DISCORD_BOT_TOKEN` | Discord REST v10 | yes (send/edit/reply/react/thread) | stdlib `urllib`; exposes `delete-message` |
| `google_news.py` | `GNEWS_API_KEY` | GNews REST | no | stdlib `urllib` + `re` |
| `ga4.py` | `GOOGLE_APPLICATION_CREDENTIALS`, `GA4_PROPERTY_ID` | GA4 Data API | no | needs `google-analytics-data` |
| `gsc.py` | OAuth `client_secrets`/`token` | Search Console | no | needs `google-api-python-client`, `google-auth-oauthlib` |
| `openobserve.py` | `O2_URL`/`O2_TOKEN`/`O2_ORG` | OpenObserve REST | read + queries | stdlib `urllib` |
| `cc_usage.py` | — | local `~/.claude` files | no | no network; reads JSONL |
| `bitwarden.py` | `BW_SESSION` | `bw` CLI (subprocess) | no | no HTTP |
| `desktop.py` | — | macOS via subprocess | local side effects | no HTTP |

"API-call scripts" (contract candidates) are the seven that reach a remote HTTP
API: openrouter, linear, discord, google_news, ga4, gsc, openobserve.
`cc_usage`, `bitwarden`, and `desktop` are covered by unit + integration only.

## Tooling

- **pytest** with three registered markers: `unit`, `integration`, `contract`.
- `pytest.ini` sets `addopts = -m "not contract"` so a bare `pytest` runs only
  unit + integration and never touches a live API by accident. Run contract
  explicitly with `pytest -m contract`.
- `requirements-dev.txt` pins: `pytest`, `google-analytics-data`,
  `google-api-python-client`, `google-auth-oauthlib`. The google libs are
  installed so `ga4.py`/`gsc.py` can be **imported and mocked** in integration
  and CI. Real google **credentials** are required only for contract tests.

### Importing the scripts

Scripts are standalone files in hyphenated directories, not an installable
package. `tests/conftest.py` provides `load_script(name)` which loads a script
module by its file path via `importlib.util`. Tests use it to:

- call internal functions directly (unit), or
- drive `main()` with patched `sys.argv` and patched `urlopen`/`subprocess.run`
  (integration, contract).

A module-level cache avoids re-importing the same script across tests.

## Layout (repository root)

```
tests/
  conftest.py            # load_script, env/lib skip helpers, fake-urlopen factory
  unit/
    test_openrouter_unit.py
    test_linear_unit.py
    ...                  # one file per script
  integration/
    test_openrouter_integration.py
    ...                  # one file per script
  contract/
    test_openrouter_contract.py
    ...                  # one file per API script
  fixtures/
    <script>/...         # canned API JSON responses for integration
  README.md              # required env vars + script -> suite coverage matrix
requirements-dev.txt
pytest.ini
.github/workflows/tests.yml
```

Tests sit at the repo root (not nested under `pai-tools`) because tests and CI
are a repo-wide concern and CI runs from the root.

## Suite 1: unit (no network, no keys)

Targets the pure, side-effect-free logic in each script. Representative targets:

- **openrouter**: `per_million_tokens` (free / zero / numeric), `format_dollars`,
  model filtering by search term, the 20-item truncation cap.
- **linear**: `priority_name` boundary values, list-issues filter/condition
  construction, the "labels not found" error branch.
- **discord**: `check_len` at the 2000-char boundary, channel-type filtering
  (types 0 and 5), sort-by-position.
- **google_news**: query building / regex text cleaning.
- **openobserve**: time-range parsing, SQL construction, field redaction.
- **ga4**: property-id precedence (arg over env), date handling.
- **gsc**: date-range computation, credential/token path resolution.
- **cc_usage**: date-window aggregation over a fixture config dir
  (`CLAUDE_CONFIG_DIR` pointed at `tests/fixtures/cc_usage/`).
- **bitwarden**: parsing/formatting of `bw` JSON output (`subprocess.run` mocked).
- **desktop**: subprocess command construction for screencapture/osascript
  (`subprocess.run` mocked).

Rule: a function is unit-tested only if it is pure. Logic welded to a network
call is exercised in integration instead.

## Suite 2: integration (mocked HTTP/subprocess, no keys)

Drives **every subcommand of every script** through `main()`:

1. Set fake env vars so each `get_api_key()` / token check passes.
2. Monkeypatch the script module's `urlopen` (or `subprocess.run` for bitwarden
   and desktop; the google client classes for ga4/gsc) to return canned
   responses loaded from `tests/fixtures/<script>/`.
3. Patch `sys.argv`, capture stdout with `capsys`.
4. Assert **both**:
   - the rendered stdout, and
   - the request the command built — URL, method, headers, and JSON body —
     by inspecting the `Request` object passed to the fake `urlopen`.

Error paths are covered too: `HTTPError -> sys.exit(message)`, "not found"
branches, missing-argument exits. Full subcommand coverage here is what
exercises the full toolset and proves each command does what its docstring says.

ga4/gsc integration tests patch the google client objects, so they require the
google libs to be importable (provided by `requirements-dev.txt`) but no real
credentials.

## Suite 3: contract (real keys, live APIs, auto-skipping)

Each test skips unless its prerequisites are present, via helpers in
`conftest.py`:

- `requires_env(*names)` — skip when any env var is unset.
- `requires_module(name)` — skip when an optional lib is not importable.

**Read commands** call the live API and assert the response still carries the
fields the script depends on — the actual contract check (the live schema has
not drifted from what the script parses).

**Mutating commands** use create -> assert -> cleanup with `try/finally`
fixtures so artifacts are removed even when an assertion fails:

- **Discord** (`DISCORD_TEST_CHANNEL_ID`): `send-message` -> assert ->
  `delete-message`, all through the CLI. Optionally exercise reply / edit /
  add-reaction / create-thread, each cleaned up.
- **Linear** (`LINEAR_TEST_TEAM`): `create-issue` -> assert -> teardown via a
  direct GraphQL `issueDelete` in the fixture finalizer (the CLI has no delete
  command, so cleanup bypasses it; the script under test is unchanged).

ga4/gsc contract tests auto-skip unless their credentials and libs are present.

Contract-only env vars (`DISCORD_TEST_CHANNEL_ID`, `LINEAR_TEST_TEAM`, plus the
per-script auth vars) are documented in `tests/README.md`.

## Running

```
pytest                      # unit + integration (default; contract deselected)
pytest -m unit
pytest -m integration
pytest -m contract          # opt-in; needs real keys
```

## CI

`.github/workflows/tests.yml`:

- Trigger on push and pull_request.
- One Python version (3.12).
- `pip install -r requirements-dev.txt`.
- `pytest -m "unit or integration"`.
- No secrets; contract is never run in CI.

## Coverage guarantee

- Unit + integration together touch all ten scripts and every subcommand.
- Contract covers the seven API scripts (five stdlib always; ga4/gsc when
  credentials exist).
- `tests/README.md` carries a script -> suite matrix so any gap is visible.

## Out of scope

- Testing `SKILL.md` / README prose.
- A linter for plugin manifests (could be a later, separate effort).
- Mutating-write coverage for scripts beyond Linear and Discord (no other
  script mutates remote state).
