---
name: strava
description: Use when reading Strava data from a Claude Code session — your athlete profile and stats, activities and their comments/kudos/laps/zones/streams, clubs, gear, routes (incl. GPX/TCX export), segments, segment efforts, and upload status. Read-only wrapper for the Strava API v3. Stdlib-only Python; auto-refreshes the rotating OAuth token.
---

# Strava

Read [Strava](https://www.strava.com) data through the [API v3](https://developers.strava.com/docs/reference/). Stdlib-only Python CLI. **Read-only** — no endpoint here creates, updates, uploads, or stars anything.

## When to use

- "How far did I run last week?" / "Show my last 10 activities."
- "What's the heart-rate stream summary for activity 12345?"
- "List the segments in this bounding box" / "My starred segments."
- "Export route 555 as GPX."
- "What are my all-time run totals?"

## When NOT to use

- You need to **create, edit, upload, or star** anything — this skill is read-only by design. Use the Strava app/web for writes.
- You need webhook/push-subscription management — not covered.
- The data crosses a scope you didn't grant. A call that returns `401`/`403` after a successful token refresh usually means the OAuth token lacks the scope (e.g. `activity:read_all` for private activities).

## Setup (one time)

Your app's credentials and a user token. Client ID is not secret; the secret and tokens are.

```bash
export STRAVA_CLIENT_ID="271296"
export STRAVA_CLIENT_SECRET="..."      # app secret
export STRAVA_ACCESS_TOKEN="..."       # seed access token
export STRAVA_REFRESH_TOKEN="..."      # seed refresh token
# optional: override where refreshed tokens are cached
# export STRAVA_TOKEN_PATH="$HOME/.strava_token.json"
```

**Token refresh is automatic.** Access tokens live ~6h and Strava **rotates the refresh token on every refresh** (the old one dies immediately). The script persists refreshed tokens to a `0600` cache file (default: `.strava_token.json` next to the script, gitignored). After the first refresh, that file — not your env vars — is the source of truth. Don't commit it.

## Invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/strava/scripts/strava.py" athlete

python3 "${CLAUDE_PLUGIN_ROOT}/skills/strava/scripts/strava.py" \
  activities --after 2026-01-01 --per-page 10

python3 "${CLAUDE_PLUGIN_ROOT}/skills/strava/scripts/strava.py" activity 1234567890

python3 "${CLAUDE_PLUGIN_ROOT}/skills/strava/scripts/strava.py" \
  activity-streams 1234567890 --keys time,heartrate,watts

python3 "${CLAUDE_PLUGIN_ROOT}/skills/strava/scripts/strava.py" \
  segments-explore --bounds 45.4,-75.8,45.5,-75.6 --activity-type riding
```

Add `--json` to **any** subcommand to get the raw API JSON instead of the human summary — the right choice when you need to parse fields programmatically.

## Subcommands

Athlete:
- `athlete` — authenticated athlete profile
- `athlete-zones` — heart-rate / power zones
- `athlete-stats [--id N]` — totals (recent / YTD / all-time); id defaults to you
- `athlete-clubs` — clubs you belong to
- `athlete-routes [--id N] [--page] [--per-page]`

Activities:
- `activities [--before DATE|EPOCH] [--after DATE|EPOCH] [--page] [--per-page]`
- `activity ID`
- `activity-comments ID [--page] [--per-page]`
- `activity-kudos ID [--page] [--per-page]`
- `activity-laps ID`
- `activity-zones ID`
- `activity-streams ID [--keys a,b,c] [--raw]`

Clubs: `club ID`, `club-activities ID`, `club-members ID`, `club-admins ID`

Gear: `gear ID`

Routes:
- `route ID`
- `route-export ID --format gpx|tcx` — prints the raw GPX/TCX
- `route-streams ID`

Segments:
- `segment ID`
- `segments-starred [--page] [--per-page]`
- `segments-explore --bounds SW_LAT,SW_LNG,NE_LAT,NE_LNG [--activity-type running|riding] [--min-cat N] [--max-cat N]`
- `segment-streams ID`

Segment efforts:
- `segment-efforts SEGMENT_ID [--athlete-effort] [--start ISO] [--end ISO] [--per-page]`
- `segment-effort ID`
- `segment-effort-streams ID`

Uploads: `upload ID` — poll the status of a prior upload

Notes:
- `--before`/`--after` accept an ISO date (`YYYY-MM-DD`) or a raw epoch integer.
- `--per-page` is capped at 200 (Strava's max).
- Streams print a summary (type + point count) by default; `--raw` (or `--json`) emits the full per-point arrays.

## Rules

- **Read-only.** This skill never writes to Strava. If you need a write, do it in the app.
- **`STRAVA_CLIENT_SECRET` and the tokens are credentials.** The script never echoes them. The token cache file holds your rotating refresh token — treat it like a secret and never commit it.
- **Rate limits (Standard tier): 200 requests / 15 min, 2000 / day.** A `429` prints the `X-RateLimit-Usage`/`Limit` headers so you can see where you stand; wait and retry rather than hammering.
- **Streams and activity lists can be large.** Prefer the default summaries and pagination; reach for `--raw`/`--json` only when you actually need the full data, to avoid flooding context.
- **Pair with `auditing-for-confidential-data`** before pasting Strava output (locations, routes, home/start coordinates) anywhere public — activity GPS and `start_latlng` can reveal where you live.
