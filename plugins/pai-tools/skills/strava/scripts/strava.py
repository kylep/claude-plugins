#!/usr/bin/env python3
"""Strava CLI — read-only wrapper for the Strava API v3.

Fresh stdlib-only wrapper (urllib). Covers the documented GET endpoints across
athletes, activities, clubs, gear, routes, segments, segment efforts, streams,
and uploads. No write/mutating endpoints are exposed.

Auth: Strava access tokens expire ~6h and the refresh token ROTATES on every
refresh (the old one dies immediately). This script seeds from env vars, then
persists refreshed tokens to a gitignored cache file so subsequent runs reuse
them.

Setup:
  export STRAVA_CLIENT_ID="271296"
  export STRAVA_CLIENT_SECRET="..."
  export STRAVA_ACCESS_TOKEN="..."
  export STRAVA_REFRESH_TOKEN="..."
  # optional: export STRAVA_TOKEN_PATH="/path/to/.strava_token.json"

Usage:
  strava.py athlete
  strava.py activities [--before DATE|EPOCH] [--after DATE|EPOCH] [--page N] [--per-page N]
  strava.py activity ID
  strava.py activity-streams ID [--keys time,latlng,heartrate] [--raw]
  strava.py segments-explore --bounds SW_LAT,SW_LNG,NE_LAT,NE_LNG [--activity-type running|riding]
  ... (see --help for the full list)

Any subcommand accepts --json to dump the raw API JSON instead of a summary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"
AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
DEFAULT_SCOPE = "read,activity:read_all,profile:read_all"
SCRIPT_DIR = Path(__file__).parent
EXPIRY_BUFFER = 60  # refresh this many seconds before actual expiry

# All documented stream types; requested by default (summary only shows counts).
STREAM_KEYS = [
    "time",
    "distance",
    "latlng",
    "altitude",
    "velocity_smooth",
    "heartrate",
    "cadence",
    "watts",
    "temp",
    "moving",
    "grade_smooth",
]


# ---------------------------------------------------------------------------
# Env + token cache
# ---------------------------------------------------------------------------


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(f"{name} environment variable is not set")
    return val


def token_cache_path() -> Path:
    return Path(os.environ.get("STRAVA_TOKEN_PATH", SCRIPT_DIR / ".strava_token.json"))


def load_token_cache() -> dict:
    """Load the token cache, or seed it from env vars (marked expired)."""
    path = token_cache_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("access_token") and data.get("refresh_token"):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "access_token": require_env("STRAVA_ACCESS_TOKEN"),
        "refresh_token": require_env("STRAVA_REFRESH_TOKEN"),
        "expires_at": 0,  # unknown -> treat as expired, force a refresh
    }


def save_token_cache(data: dict) -> None:
    path = token_cache_path()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_at": data["expires_at"],
            },
            fh,
        )


def is_token_expired(expires_at, now: float | None = None) -> bool:
    if now is None:
        now = time.time()
    try:
        return float(expires_at) <= now + EXPIRY_BUFFER
    except (TypeError, ValueError):
        return True


def refresh_tokens(refresh_token: str) -> dict:
    """POST to the OAuth token endpoint and persist the rotated tokens."""
    body = urlencode(
        {
            "client_id": require_env("STRAVA_CLIENT_ID"),
            "client_secret": require_env("STRAVA_CLIENT_SECRET"),
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    req = Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        sys.exit(
            f"Strava token refresh failed (HTTP {e.code}): "
            f"{e.read().decode('utf-8', errors='replace')}"
        )
    cache = {
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "expires_at": payload["expires_at"],
    }
    save_token_cache(cache)
    return cache


def get_access_token(force_refresh: bool = False) -> str:
    cache = load_token_cache()
    if force_refresh or is_token_expired(cache.get("expires_at", 0)):
        cache = refresh_tokens(cache["refresh_token"])
    return cache["access_token"]


# ---------------------------------------------------------------------------
# One-time OAuth (authorize URL + code exchange)
# ---------------------------------------------------------------------------


def build_authorize_url(scope: str, redirect_uri: str) -> str:
    params = {
        "client_id": require_env("STRAVA_CLIENT_ID"),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "force",
        "scope": scope,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Exchange an authorization code for tokens and persist them to the cache."""
    body = urlencode(
        {
            "client_id": require_env("STRAVA_CLIENT_ID"),
            "client_secret": require_env("STRAVA_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        sys.exit(
            f"Strava token exchange failed (HTTP {e.code}): "
            f"{e.read().decode('utf-8', errors='replace')}"
        )
    save_token_cache(
        {
            "access_token": payload["access_token"],
            "refresh_token": payload["refresh_token"],
            "expires_at": payload["expires_at"],
        }
    )
    return payload


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _rate_limit_note(headers) -> str:
    usage = headers.get("X-RateLimit-Usage")
    limit = headers.get("X-RateLimit-Limit")
    if usage or limit:
        return f" (X-RateLimit-Usage: {usage or '?'}, X-RateLimit-Limit: {limit or '?'})"
    return ""


def _do_request(path: str, params: dict | None, token: str):
    url = BASE_URL + path
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url = f"{url}?{urlencode(clean)}"
    req = Request(url, method="GET", headers={"Authorization": f"Bearer {token}"})
    return urlopen(req, timeout=30)


def _handle_http_error(e: HTTPError) -> None:
    if e.code == 429:
        sys.exit(
            "Strava API rate limit exceeded (HTTP 429)"
            f"{_rate_limit_note(e.headers)}. Standard tier allows 200 req/15min "
            "and 2000/day. Wait and retry."
        )
    sys.exit(
        f"Strava API HTTP error {e.code}: "
        f"{e.read().decode('utf-8', errors='replace')}"
    )


def api(path: str, params: dict | None = None):
    """GET a JSON endpoint. Refreshes reactively on 401 and retries once."""
    token = get_access_token()
    try:
        with _do_request(path, params, token) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 401:
            token = get_access_token(force_refresh=True)
            try:
                with _do_request(path, params, token) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as e2:
                _handle_http_error(e2)
        _handle_http_error(e)


def api_text(path: str, params: dict | None = None) -> str:
    """GET a non-JSON endpoint (GPX/TCX export). Same 401 retry behaviour."""
    token = get_access_token()
    try:
        with _do_request(path, params, token) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as e:
        if e.code == 401:
            token = get_access_token(force_refresh=True)
            try:
                with _do_request(path, params, token) as resp:
                    return resp.read().decode("utf-8")
            except HTTPError as e2:
                _handle_http_error(e2)
        _handle_http_error(e)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def fmt_distance(meters) -> str:
    try:
        return f"{float(meters) / 1000:.2f} km"
    except (TypeError, ValueError):
        return "—"


def fmt_duration(seconds) -> str:
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "—"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def clamp_per_page(n: int) -> int:
    return max(1, min(int(n), 200))


def parse_time(value: str | None):
    """Accept an ISO date (YYYY-MM-DD) or a raw epoch int; return epoch seconds."""
    if value is None:
        return None
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    from datetime import datetime, timezone

    try:
        dt = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        sys.exit(f"Invalid date/epoch '{value}'. Use YYYY-MM-DD or an epoch integer.")
    return int(dt.timestamp())


def parse_bounds(value: str) -> str:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        sys.exit("--bounds must be SW_LAT,SW_LNG,NE_LAT,NE_LNG (four values).")
    try:
        [float(p) for p in parts]
    except ValueError:
        sys.exit("--bounds values must all be numbers.")
    return ",".join(parts)


def stream_summary(data) -> list[str]:
    """Summarize a key_by_type=true streams payload as 'type: N points'."""
    lines = []
    if isinstance(data, dict):
        for key, stream in data.items():
            points = len(stream.get("data", [])) if isinstance(stream, dict) else "?"
            lines.append(f"  {key}: {points} points")
    elif isinstance(data, list):
        for stream in data:
            key = stream.get("type", "?")
            points = len(stream.get("data", []))
            lines.append(f"  {key}: {points} points")
    return lines


def emit_json(data) -> None:
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Auth command
# ---------------------------------------------------------------------------


def cmd_auth(args) -> None:
    if not args.code:
        url = build_authorize_url(args.scope, args.redirect_uri)
        print("1. Open this URL and click Authorize (leave every requested scope checked):\n")
        print(url)
        print(
            "\n2. Your browser redirects to your callback. It may show a 404 or "
            "'can't connect' — that is fine. Copy the `code` value out of the "
            "address-bar URL:  ...?state=&code=THIS_PART&scope=...\n"
        )
        print("3. Re-run:  strava.py auth --code THAT_CODE\n")
        print(
            "If the redirect is rejected outright (not a 404), your app's "
            "'Authorization Callback Domain' does not match the redirect host — set "
            f"it to match '{args.redirect_uri}' (default 'localhost') in the Strava "
            "app settings, then retry."
        )
        return
    payload = exchange_code(args.code)
    if args.json:
        return emit_json(payload)
    athlete = payload.get("athlete") or {}
    who = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
    print("Authorized. Tokens written to the cache — the CLI works now.")
    if who or athlete.get("id"):
        print(f"Athlete: {who or '—'} (id: {athlete.get('id')})")
    print("\nPersist these in exports.sh so a cache wipe doesn't lose them:")
    print(f'  export STRAVA_ACCESS_TOKEN="{payload["access_token"]}"')
    print(f'  export STRAVA_REFRESH_TOKEN="{payload["refresh_token"]}"')


# ---------------------------------------------------------------------------
# Athlete commands
# ---------------------------------------------------------------------------


def cmd_athlete(args) -> None:
    data = api("/athlete")
    if args.json:
        return emit_json(data)
    name = f"{data.get('firstname', '')} {data.get('lastname', '')}".strip()
    print(f"# {name}  (id: {data.get('id')})")
    for field in ("username", "city", "state", "country", "sex", "weight"):
        if data.get(field) not in (None, ""):
            print(f"{field.capitalize():<10} {data[field]}")


def cmd_athlete_zones(args) -> None:
    data = api("/athlete/zones")
    if args.json:
        return emit_json(data)
    hr = (data.get("heart_rate") or {}).get("zones") or []
    power = (data.get("power") or {}).get("zones") or []
    print(f"Heart rate zones: {len(hr)}")
    for i, z in enumerate(hr, 1):
        print(f"  Z{i}: {z.get('min')}–{z.get('max')}")
    print(f"Power zones: {len(power)}")
    for i, z in enumerate(power, 1):
        print(f"  Z{i}: {z.get('min')}–{z.get('max')}")


def _resolve_athlete_id(explicit) -> int:
    if explicit is not None:
        return explicit
    return api("/athlete")["id"]


def cmd_athlete_stats(args) -> None:
    athlete_id = _resolve_athlete_id(args.id)
    data = api(f"/athletes/{athlete_id}/stats")
    if args.json:
        return emit_json(data)
    print(f"# Stats for athlete {athlete_id}")
    for key in ("recent_run_totals", "recent_ride_totals", "ytd_run_totals",
                "ytd_ride_totals", "all_run_totals", "all_ride_totals"):
        totals = data.get(key)
        if totals:
            print(
                f"{key:<20} {totals.get('count', 0)} activities, "
                f"{fmt_distance(totals.get('distance'))}"
            )


def cmd_athlete_clubs(args) -> None:
    data = api("/athlete/clubs")
    if args.json:
        return emit_json(data)
    if not data:
        print("No clubs.")
        return
    for c in data:
        print(f"  [{c.get('id')}] {c.get('name')}  ({c.get('member_count', '?')} members)")


def cmd_athlete_routes(args) -> None:
    athlete_id = _resolve_athlete_id(args.id)
    data = api(
        f"/athletes/{athlete_id}/routes",
        {"page": args.page, "per_page": clamp_per_page(args.per_page)},
    )
    if args.json:
        return emit_json(data)
    if not data:
        print("No routes.")
        return
    for r in data:
        print(f"  [{r.get('id')}] {r.get('name')}  {fmt_distance(r.get('distance'))}")


# ---------------------------------------------------------------------------
# Activity commands
# ---------------------------------------------------------------------------


def cmd_activities(args) -> None:
    params = {
        "page": args.page,
        "per_page": clamp_per_page(args.per_page),
        "before": parse_time(args.before),
        "after": parse_time(args.after),
    }
    data = api("/athlete/activities", params)
    if args.json:
        return emit_json(data)
    if not data:
        print("No activities found.")
        return
    for a in data:
        print(
            f"  [{a.get('id')}] {a.get('start_date_local', '')[:10]}  "
            f"{a.get('type', '?'):<12} {fmt_distance(a.get('distance')):>10}  "
            f"{fmt_duration(a.get('moving_time')):>8}  {a.get('name')}"
        )


def cmd_activity(args) -> None:
    data = api(f"/activities/{args.id}")
    if args.json:
        return emit_json(data)
    print(f"# {data.get('name')}  (id: {data.get('id')})")
    print(f"Type:      {data.get('type')}")
    print(f"Date:      {data.get('start_date_local')}")
    print(f"Distance:  {fmt_distance(data.get('distance'))}")
    print(f"Moving:    {fmt_duration(data.get('moving_time'))}")
    print(f"Elapsed:   {fmt_duration(data.get('elapsed_time'))}")
    print(f"Elevation: {data.get('total_elevation_gain', '—')} m")
    if data.get("average_speed") is not None:
        print(f"Avg speed: {data['average_speed']} m/s")
    if data.get("average_heartrate") is not None:
        print(f"Avg HR:    {data['average_heartrate']}")
    if data.get("description"):
        print(f"\n{data['description']}")


def cmd_activity_comments(args) -> None:
    data = api(
        f"/activities/{args.id}/comments",
        {"page": args.page, "per_page": clamp_per_page(args.per_page)},
    )
    if args.json:
        return emit_json(data)
    if not data:
        print("No comments.")
        return
    for c in data:
        athlete = c.get("athlete") or {}
        who = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
        print(f"[{c.get('created_at', '')}] {who or '—'}: {c.get('text', '')}")


def cmd_activity_kudos(args) -> None:
    data = api(
        f"/activities/{args.id}/kudos",
        {"page": args.page, "per_page": clamp_per_page(args.per_page)},
    )
    if args.json:
        return emit_json(data)
    if not data:
        print("No kudos.")
        return
    for k in data:
        print(f"  {k.get('firstname', '')} {k.get('lastname', '')}".rstrip())


def cmd_activity_laps(args) -> None:
    data = api(f"/activities/{args.id}/laps")
    if args.json:
        return emit_json(data)
    if not data:
        print("No laps.")
        return
    for lap in data:
        print(
            f"  Lap {lap.get('lap_index', '?')}: "
            f"{fmt_distance(lap.get('distance'))}  "
            f"{fmt_duration(lap.get('moving_time'))}"
        )


def cmd_activity_zones(args) -> None:
    data = api(f"/activities/{args.id}/zones")
    if args.json:
        return emit_json(data)
    if not data:
        print("No zones.")
        return
    for z in data:
        buckets = z.get("distribution_buckets") or []
        print(f"  {z.get('type', '?')}: {len(buckets)} buckets")


def cmd_activity_streams(args) -> None:
    keys = args.keys or ",".join(STREAM_KEYS)
    data = api(
        f"/activities/{args.id}/streams",
        {"keys": keys, "key_by_type": "true"},
    )
    if args.json or args.raw:
        return emit_json(data)
    print(f"# Streams for activity {args.id}")
    lines = stream_summary(data)
    print("\n".join(lines) if lines else "  (no streams)")


# ---------------------------------------------------------------------------
# Club commands
# ---------------------------------------------------------------------------


def cmd_club(args) -> None:
    data = api(f"/clubs/{args.id}")
    if args.json:
        return emit_json(data)
    print(f"# {data.get('name')}  (id: {data.get('id')})")
    print(f"Sport:   {data.get('sport_type', '—')}")
    print(f"Members: {data.get('member_count', '—')}")
    print(f"Location: {data.get('city', '')}, {data.get('country', '')}".rstrip(", "))


def cmd_club_activities(args) -> None:
    data = api(
        f"/clubs/{args.id}/activities",
        {"page": args.page, "per_page": clamp_per_page(args.per_page)},
    )
    if args.json:
        return emit_json(data)
    if not data:
        print("No activities.")
        return
    for a in data:
        athlete = a.get("athlete") or {}
        who = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
        print(
            f"  {who or '—':<20} {a.get('type', '?'):<10} "
            f"{fmt_distance(a.get('distance'))}  {a.get('name')}"
        )


def cmd_club_members(args) -> None:
    data = api(
        f"/clubs/{args.id}/members",
        {"page": args.page, "per_page": clamp_per_page(args.per_page)},
    )
    if args.json:
        return emit_json(data)
    if not data:
        print("No members.")
        return
    for m in data:
        admin = " (admin)" if m.get("admin") else ""
        print(f"  {m.get('firstname', '')} {m.get('lastname', '')}{admin}".strip())


def cmd_club_admins(args) -> None:
    data = api(
        f"/clubs/{args.id}/admins",
        {"page": args.page, "per_page": clamp_per_page(args.per_page)},
    )
    if args.json:
        return emit_json(data)
    if not data:
        print("No admins.")
        return
    for m in data:
        print(f"  {m.get('firstname', '')} {m.get('lastname', '')}".strip())


# ---------------------------------------------------------------------------
# Gear
# ---------------------------------------------------------------------------


def cmd_gear(args) -> None:
    data = api(f"/gears/{args.id}")
    if args.json:
        return emit_json(data)
    print(f"# {data.get('name')}  (id: {data.get('id')})")
    print(f"Brand:    {data.get('brand_name', '—')}")
    print(f"Model:    {data.get('model_name', '—')}")
    print(f"Distance: {fmt_distance(data.get('distance'))}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def cmd_route(args) -> None:
    data = api(f"/routes/{args.id}")
    if args.json:
        return emit_json(data)
    print(f"# {data.get('name')}  (id: {data.get('id')})")
    print(f"Distance:  {fmt_distance(data.get('distance'))}")
    print(f"Elevation: {data.get('elevation_gain', '—')} m")
    print(f"Type:      {data.get('type', '—')}")
    if data.get("description"):
        print(f"\n{data['description']}")


def cmd_route_export(args) -> None:
    text = api_text(f"/routes/{args.id}/{args.format}")
    print(text)


def cmd_route_streams(args) -> None:
    data = api(f"/routes/{args.id}/streams")
    if args.json or args.raw:
        return emit_json(data)
    print(f"# Streams for route {args.id}")
    lines = stream_summary(data)
    print("\n".join(lines) if lines else "  (no streams)")


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------


def cmd_segment(args) -> None:
    data = api(f"/segments/{args.id}")
    if args.json:
        return emit_json(data)
    print(f"# {data.get('name')}  (id: {data.get('id')})")
    print(f"Activity:  {data.get('activity_type', '—')}")
    print(f"Distance:  {fmt_distance(data.get('distance'))}")
    print(f"Avg grade: {data.get('average_grade', '—')}%")
    print(f"Category:  {data.get('climb_category', '—')}")


def cmd_segments_starred(args) -> None:
    data = api(
        "/segments/starred",
        {"page": args.page, "per_page": clamp_per_page(args.per_page)},
    )
    if args.json:
        return emit_json(data)
    if not data:
        print("No starred segments.")
        return
    for s in data:
        print(
            f"  [{s.get('id')}] {s.get('name')}  "
            f"{fmt_distance(s.get('distance'))}  {s.get('average_grade', '—')}%"
        )


def cmd_segments_explore(args) -> None:
    params = {
        "bounds": parse_bounds(args.bounds),
        "activity_type": args.activity_type,
        "min_cat": args.min_cat,
        "max_cat": args.max_cat,
    }
    data = api("/segments/explore", params)
    if args.json:
        return emit_json(data)
    segments = data.get("segments") or []
    if not segments:
        print("No segments found.")
        return
    for s in segments:
        print(
            f"  [{s.get('id')}] {s.get('name')}  "
            f"{fmt_distance(s.get('distance'))}  cat {s.get('climb_category', '—')}"
        )


def cmd_segment_streams(args) -> None:
    data = api(f"/segments/{args.id}/streams")
    if args.json or args.raw:
        return emit_json(data)
    print(f"# Streams for segment {args.id}")
    lines = stream_summary(data)
    print("\n".join(lines) if lines else "  (no streams)")


# ---------------------------------------------------------------------------
# Segment efforts
# ---------------------------------------------------------------------------


def cmd_segment_efforts(args) -> None:
    params = {
        "segment_id": args.segment_id,
        "per_page": clamp_per_page(args.per_page),
        "start_date_local": args.start,
        "end_date_local": args.end,
    }
    data = api("/segment_efforts", params) if args.athlete_effort else api(
        f"/segments/{args.segment_id}/all_efforts",
        {
            "per_page": clamp_per_page(args.per_page),
            "start_date_local": args.start,
            "end_date_local": args.end,
        },
    )
    if args.json:
        return emit_json(data)
    if not data:
        print("No efforts.")
        return
    for e in data:
        athlete = e.get("athlete") or {}
        print(
            f"  [{e.get('id')}] {e.get('start_date_local', '')[:10]}  "
            f"{fmt_duration(e.get('elapsed_time'))}  athlete {athlete.get('id', '—')}"
        )


def cmd_segment_effort(args) -> None:
    data = api(f"/segment_efforts/{args.id}")
    if args.json:
        return emit_json(data)
    seg = data.get("segment") or {}
    print(f"# Effort {data.get('id')} on {seg.get('name', '—')}")
    print(f"Date:    {data.get('start_date_local')}")
    print(f"Elapsed: {fmt_duration(data.get('elapsed_time'))}")
    print(f"Moving:  {fmt_duration(data.get('moving_time'))}")
    print(f"Distance: {fmt_distance(data.get('distance'))}")


def cmd_segment_effort_streams(args) -> None:
    data = api(f"/segment_efforts/{args.id}/streams")
    if args.json or args.raw:
        return emit_json(data)
    print(f"# Streams for segment effort {args.id}")
    lines = stream_summary(data)
    print("\n".join(lines) if lines else "  (no streams)")


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------


def cmd_upload(args) -> None:
    data = api(f"/uploads/{args.id}")
    if args.json:
        return emit_json(data)
    print(f"# Upload {data.get('id')}")
    print(f"Status:      {data.get('status')}")
    print(f"Activity id: {data.get('activity_id', '—')}")
    if data.get("error"):
        print(f"Error:       {data['error']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _add_pagination(p) -> None:
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--per-page", type=int, default=30, dest="per_page")


def build_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--json", action="store_true", help="Dump raw API JSON instead of a summary."
    )

    parser = argparse.ArgumentParser(prog="strava.py", description="Strava read-only CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "auth",
        parents=[parent],
        help="One-time OAuth: print the authorize URL, or exchange a code for tokens.",
    )
    p.add_argument("--code", help="Authorization code from the redirect URL.")
    p.add_argument("--scope", default=DEFAULT_SCOPE, help="Comma-separated scopes to request.")
    p.add_argument(
        "--redirect-uri", default="http://localhost", dest="redirect_uri",
        help="Must match your app's Authorization Callback Domain (default localhost).",
    )

    sub.add_parser("athlete", parents=[parent], help="Authenticated athlete profile.")
    sub.add_parser("athlete-zones", parents=[parent], help="HR/power zones.")

    p = sub.add_parser("athlete-stats", parents=[parent], help="Athlete totals.")
    p.add_argument("--id", type=int, help="Athlete id (default: authenticated).")

    sub.add_parser("athlete-clubs", parents=[parent], help="Clubs you belong to.")

    p = sub.add_parser("athlete-routes", parents=[parent], help="Your routes.")
    p.add_argument("--id", type=int, help="Athlete id (default: authenticated).")
    _add_pagination(p)

    p = sub.add_parser("activities", parents=[parent], help="List your activities.")
    p.add_argument("--before", help="ISO date or epoch: only activities before.")
    p.add_argument("--after", help="ISO date or epoch: only activities after.")
    _add_pagination(p)

    p = sub.add_parser("activity", parents=[parent], help="One activity by id.")
    p.add_argument("id")

    p = sub.add_parser("activity-comments", parents=[parent], help="Activity comments.")
    p.add_argument("id")
    _add_pagination(p)

    p = sub.add_parser("activity-kudos", parents=[parent], help="Activity kudoers.")
    p.add_argument("id")
    _add_pagination(p)

    p = sub.add_parser("activity-laps", parents=[parent], help="Activity laps.")
    p.add_argument("id")

    p = sub.add_parser("activity-zones", parents=[parent], help="Activity HR/power zones.")
    p.add_argument("id")

    p = sub.add_parser("activity-streams", parents=[parent], help="Activity streams.")
    p.add_argument("id")
    p.add_argument("--keys", help="Comma-separated stream types.")
    p.add_argument("--raw", action="store_true", help="Full arrays, not a summary.")

    p = sub.add_parser("club", parents=[parent], help="Club detail.")
    p.add_argument("id")

    p = sub.add_parser("club-activities", parents=[parent], help="Club activities.")
    p.add_argument("id")
    _add_pagination(p)

    p = sub.add_parser("club-members", parents=[parent], help="Club members.")
    p.add_argument("id")
    _add_pagination(p)

    p = sub.add_parser("club-admins", parents=[parent], help="Club admins.")
    p.add_argument("id")
    _add_pagination(p)

    p = sub.add_parser("gear", parents=[parent], help="Gear/equipment detail.")
    p.add_argument("id")

    p = sub.add_parser("route", parents=[parent], help="Route detail.")
    p.add_argument("id")

    p = sub.add_parser("route-export", parents=[parent], help="Export route GPX/TCX.")
    p.add_argument("id")
    p.add_argument("--format", choices=["gpx", "tcx"], required=True)

    p = sub.add_parser("route-streams", parents=[parent], help="Route streams.")
    p.add_argument("id")
    p.add_argument("--raw", action="store_true", help="Full arrays, not a summary.")

    p = sub.add_parser("segment", parents=[parent], help="Segment detail.")
    p.add_argument("id")

    p = sub.add_parser("segments-starred", parents=[parent], help="Your starred segments.")
    _add_pagination(p)

    p = sub.add_parser("segments-explore", parents=[parent], help="Explore segments in a box.")
    p.add_argument("--bounds", required=True, help="SW_LAT,SW_LNG,NE_LAT,NE_LNG")
    p.add_argument("--activity-type", choices=["running", "riding"], dest="activity_type")
    p.add_argument("--min-cat", type=int, dest="min_cat")
    p.add_argument("--max-cat", type=int, dest="max_cat")

    p = sub.add_parser("segment-streams", parents=[parent], help="Segment streams.")
    p.add_argument("id")
    p.add_argument("--raw", action="store_true", help="Full arrays, not a summary.")

    p = sub.add_parser("segment-efforts", parents=[parent], help="Efforts on a segment.")
    p.add_argument("segment_id")
    p.add_argument(
        "--athlete-effort",
        action="store_true",
        dest="athlete_effort",
        help="Your efforts across segments (uses /segment_efforts).",
    )
    p.add_argument("--start", help="start_date_local filter (ISO 8601).")
    p.add_argument("--end", help="end_date_local filter (ISO 8601).")
    p.add_argument("--per-page", type=int, default=30, dest="per_page")

    p = sub.add_parser("segment-effort", parents=[parent], help="One segment effort.")
    p.add_argument("id")

    p = sub.add_parser("segment-effort-streams", parents=[parent], help="Segment effort streams.")
    p.add_argument("id")
    p.add_argument("--raw", action="store_true", help="Full arrays, not a summary.")

    p = sub.add_parser("upload", parents=[parent], help="Poll status of a prior upload.")
    p.add_argument("id")

    return parser


DISPATCH = {
    "auth": cmd_auth,
    "athlete": cmd_athlete,
    "athlete-zones": cmd_athlete_zones,
    "athlete-stats": cmd_athlete_stats,
    "athlete-clubs": cmd_athlete_clubs,
    "athlete-routes": cmd_athlete_routes,
    "activities": cmd_activities,
    "activity": cmd_activity,
    "activity-comments": cmd_activity_comments,
    "activity-kudos": cmd_activity_kudos,
    "activity-laps": cmd_activity_laps,
    "activity-zones": cmd_activity_zones,
    "activity-streams": cmd_activity_streams,
    "club": cmd_club,
    "club-activities": cmd_club_activities,
    "club-members": cmd_club_members,
    "club-admins": cmd_club_admins,
    "gear": cmd_gear,
    "route": cmd_route,
    "route-export": cmd_route_export,
    "route-streams": cmd_route_streams,
    "segment": cmd_segment,
    "segments-starred": cmd_segments_starred,
    "segments-explore": cmd_segments_explore,
    "segment-streams": cmd_segment_streams,
    "segment-efforts": cmd_segment_efforts,
    "segment-effort": cmd_segment_effort,
    "segment-effort-streams": cmd_segment_effort_streams,
    "upload": cmd_upload,
}


def main() -> None:
    args = build_parser().parse_args()
    DISPATCH[args.command](args)


if __name__ == "__main__":
    main()
