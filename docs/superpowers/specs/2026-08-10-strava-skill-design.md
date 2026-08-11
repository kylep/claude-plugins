# Strava skill design

Date: 2026-08-10
Status: Approved

## Goal

Add a `strava` skill to the `pai-tools` plugin that wraps Strava's documented
API v3, with the widest read coverage the granted OAuth scopes expose, plus the
same three-suite test coverage (unit / integration / contract) every other
pai-tools skill has.

Scope is **read-only**: only the 19 documented `GET` endpoints. The 6 mutating
endpoints (create/update activity, upload activity, update athlete, star
segment) are deliberately excluded — they need `*:write` scopes the token may
not hold and risk altering real Strava data.

## Conventions this follows

Mirrors the existing pai-tools skills (`linear`, `gsc`, `discord`):

- Single stdlib-only Python script at
  `plugins/pai-tools/skills/strava/scripts/strava.py` (urllib, argparse, json —
  no SDK).
- `SKILL.md` with frontmatter (`name`, `description`) + When to use / When NOT /
  Setup / Invoke / Subcommands / Rules sections.
- Verb-noun subcommands dispatched from `main()`.
- Errors exit non-zero with the API error body (like `linear.py`).

## Authentication & token refresh

Strava access tokens expire ~6h and **the refresh token rotates on every
refresh** (the old refresh token dies immediately once a new one is issued).
Because a script can't rewrite the user's shell env, refreshed tokens persist to
a gitignored cache file (same idea as the `gsc` skill's `token.json`).

Env vars (all in the user's `exports.sh`, which is gitignored):

- `STRAVA_CLIENT_ID` — app client id (271296; not secret)
- `STRAVA_CLIENT_SECRET` — app secret
- `STRAVA_ACCESS_TOKEN` — seed access token
- `STRAVA_REFRESH_TOKEN` — seed refresh token
- `STRAVA_TOKEN_PATH` — optional override for the cache file location

Token resolution logic (`get_access_token()`):

1. Load token cache (`STRAVA_TOKEN_PATH`, default `SCRIPT_DIR/.strava_token.json`,
   written `0600`).
2. If no cache, seed from `STRAVA_ACCESS_TOKEN` / `STRAVA_REFRESH_TOKEN` and
   treat as expired (`expires_at = 0`).
3. If `expires_at <= now + 60` (buffer), refresh:
   `POST https://www.strava.com/oauth/token` with `client_id`, `client_secret`,
   `grant_type=refresh_token`, `refresh_token`. Persist the new access token, the
   **rotated** refresh token, and `expires_at` back to the cache.
4. Reactive fallback: if an API call returns `401` despite a "valid" cache,
   refresh once and retry the call a single time.

Missing any required env var → exit with a clear message before any network call.

`.strava_token.json` is added to `.gitignore`.

## API surface — subcommands

Base URL `https://api.strava.com/api/v3`. All 19 documented GET endpoints:

| Group | Subcommand | Endpoint |
|---|---|---|
| Athlete | `athlete` | `GET /athlete` |
| | `athlete-zones` | `GET /athlete/zones` |
| | `athlete-stats [--id N]` | `GET /athletes/{id}/stats` (id defaults to authed athlete) |
| | `athlete-clubs` | `GET /athlete/clubs` |
| | `athlete-routes [--id N] [--page] [--per-page]` | `GET /athletes/{id}/routes` |
| Activities | `activities [--before] [--after] [--page] [--per-page]` | `GET /athlete/activities` |
| | `activity ID` | `GET /activities/{id}` |
| | `activity-comments ID [--page] [--per-page]` | `GET /activities/{id}/comments` |
| | `activity-kudos ID [--page] [--per-page]` | `GET /activities/{id}/kudos` |
| | `activity-laps ID` | `GET /activities/{id}/laps` |
| | `activity-zones ID` | `GET /activities/{id}/zones` |
| | `activity-streams ID [--keys ...] [--raw]` | `GET /activities/{id}/streams` |
| Clubs | `club ID` | `GET /clubs/{id}` |
| | `club-activities ID [--page] [--per-page]` | `GET /clubs/{id}/activities` |
| | `club-members ID [--page] [--per-page]` | `GET /clubs/{id}/members` |
| | `club-admins ID [--page] [--per-page]` | `GET /clubs/{id}/admins` |
| Gear | `gear ID` | `GET /gears/{id}` |
| Routes | `route ID` | `GET /routes/{id}` |
| | `route-export ID --format gpx\|tcx` | `GET /routes/{id}/gpx` \| `/tcx` |
| | `route-streams ID` | `GET /routes/{id}/streams` |
| Segments | `segment ID` | `GET /segments/{id}` |
| | `segments-starred [--page] [--per-page]` | `GET /segments/starred` |
| | `segments-explore --bounds SW_LAT,SW_LNG,NE_LAT,NE_LNG [--activity-type running\|riding] [--min-cat] [--max-cat]` | `GET /segments/explore` |
| | `segment-streams ID` | `GET /segments/{id}/streams` |
| Segment efforts | `segment-efforts SEGMENT_ID [--athlete-effort] [--start] [--end] [--per-page]` | `GET /segments/{id}/all_efforts` |
| | `segment-effort ID` | `GET /segment_efforts/{id}` |
| | `segment-effort-streams ID` | `GET /segment_efforts/{id}/streams` |
| Uploads | `upload ID` | `GET /uploads/{id}` (poll status of a prior upload) |

## Output & error handling

- Default: human-readable summaries. Distance meters → km, moving/elapsed time →
  `h:m:s`, timestamps shown as-is. Lists print one row per item.
- Global `--json` flag on every subcommand: dump the raw API JSON for agent
  parsing (the primary path for programmatic use).
- Streams: default to a **summary** (available stream types + point count per
  type). `--raw` (or `--json`) emits the full per-point arrays. `--keys` selects
  which streams to request (comma-separated, e.g. `time,latlng,heartrate,watts`).
- Pagination: `--page` (default 1), `--per-page` (default 30, capped at 200 —
  Strava's max). `--before`/`--after` accept an ISO date (`YYYY-MM-DD`) or a raw
  epoch integer; converted to epoch seconds for the query.
- `--bounds` for `segments-explore` validated as exactly four comma-separated
  floats.
- `429` → clear rate-limit message that surfaces the `X-RateLimit-Usage` and
  `X-RateLimit-Limit` response headers. Standard tier limits are 200 req/15min
  and 2000/day.
- Other `4xx/5xx` → exit non-zero with the API error body.

## HTTP helper

`api(path, params=None)` builds `BASE_URL + path` with a urlencoded query string,
sets `Authorization: Bearer <access_token>`, `GET`s with a 30s timeout, parses
JSON, and centralizes `401` (reactive refresh + one retry), `429` (rate-limit
message), and generic HTTP error handling. A separate raw-text variant handles
`route-export` (GPX/TCX are XML, not JSON).

## Testing

Register `"strava": "strava/scripts/strava.py"` in `tests/conftest.py`'s
`SCRIPTS` dict. Reuse the existing `patch_urlopen` / `FakeUrlopen` / `run_cli` /
`http_error` / `requires_env` harness.

### unit (`tests/unit/test_strava_unit.py`)

Pure logic, no network:

- Token expiry check: expired when `expires_at <= now + buffer`, valid otherwise;
  boundary at exactly the buffer edge.
- Distance formatter (m → km), duration formatter (s → `h:m:s`), pace helper.
- `--before`/`--after` parsing: ISO date → epoch, raw epoch passthrough, invalid
  string → exit.
- `--bounds` validation: 4 floats ok; wrong count / non-numeric → exit.
- Stream summarizer: given a streams payload, produces the type/point-count
  summary.
- `--per-page` clamping to the 200 max.

### integration (`tests/integration/test_strava_integration.py`)

Mocked `urlopen`, no network, token cache pointed at `tmp_path` via
`STRAVA_TOKEN_PATH` so no real file is touched:

- Every subcommand: builds the correct URL/path + query params, sends
  `Authorization: Bearer <token>`, renders expected output. Canned payload per
  endpoint.
- Token refresh path: expired cache → `POST /oauth/token` fires → new tokens
  written to cache → original request retried with the new access token.
- Valid (unexpired) cache → **no** refresh call is made.
- Reactive `401`: first API call 401s → one refresh → retry succeeds.
- `429` → SystemExit with a message mentioning the rate-limit headers.
- Generic HTTP error and missing-env-var → SystemExit before network.
- `--json` passthrough returns raw payload.
- `route-export` returns raw GPX/TCX text (non-JSON path).

### contract (`tests/contract/test_strava_contract.py`)

Opt-in (`-m contract`), auto-skip via `requires_env`. Read-only live calls only:

- `athlete` and `activities` against the live API, gated on `STRAVA_CLIENT_ID`,
  `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`. Assert the fields the script
  depends on are present. No mutating contract tests (skill is read-only).

### Docs to update

- `README.md` (repo root) coverage matrix — add the `strava` row.
- `tests/README.md` coverage matrix + contract env-var table — add `strava`
  (read-only, auto-skip; required env `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`,
  `STRAVA_REFRESH_TOKEN`).

## Out of scope

- All 6 write endpoints (create/update/upload activity, update athlete, star
  segment).
- Webhook subscription management (push API) — not part of the read data model.
- Any local caching of activity data beyond the token cache.
