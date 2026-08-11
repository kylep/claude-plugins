import json
from urllib.parse import parse_qs, urlsplit

import pytest

from conftest import http_error, load_script, patch_urlopen, run_cli

mod = load_script("strava")
pytestmark = pytest.mark.integration

TOKEN_PAYLOAD = {
    "access_token": "new-access",
    "refresh_token": "new-refresh",
    "expires_at": 9999999999,
    "expires_in": 21600,
    "token_type": "Bearer",
}


@pytest.fixture(autouse=True)
def env_and_cache(tmp_path, monkeypatch):
    """Set required env and a far-future token cache so command tests skip refresh."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "271296")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("STRAVA_ACCESS_TOKEN", "seed-access")
    monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "seed-refresh")
    cache = tmp_path / ".strava_token.json"
    monkeypatch.setenv("STRAVA_TOKEN_PATH", str(cache))
    cache.write_text(
        json.dumps(
            {
                "access_token": "cached-access",
                "refresh_token": "cached-refresh",
                "expires_at": 9999999999,
            }
        )
    )
    return cache


def _path(req) -> str:
    return urlsplit(req.full_url).path


def _qs(req) -> dict:
    return parse_qs(urlsplit(req.full_url).query)


def _assert_get(req, token="cached-access"):
    assert req.method == "GET"
    assert req.get_header("Authorization") == f"Bearer {token}"


# ---------------------------------------------------------------------------
# Token refresh behaviour
# ---------------------------------------------------------------------------


def test_valid_cache_skips_refresh(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"id": 1, "firstname": "Kyle"})
    run_cli(mod, ["athlete"], monkeypatch)
    # Exactly one call: the GET. No token POST.
    assert len(fake.calls) == 1
    _assert_get(fake.last_request)
    assert "Kyle" in capsys.readouterr().out


def test_expired_cache_triggers_refresh_then_call(monkeypatch, capsys, env_and_cache):
    env_and_cache.write_text(
        json.dumps(
            {"access_token": "old", "refresh_token": "old-refresh", "expires_at": 0}
        )
    )
    fake = patch_urlopen(monkeypatch, mod, [TOKEN_PAYLOAD, {"id": 1, "firstname": "K"}])
    run_cli(mod, ["athlete"], monkeypatch)

    # First call is the token POST, second is the GET with the fresh token.
    token_req = fake.calls[0]
    assert token_req.method == "POST"
    assert token_req.full_url == mod.TOKEN_URL
    body = parse_qs(token_req.data.decode("utf-8"))
    assert body["grant_type"] == ["refresh_token"]
    assert body["refresh_token"] == ["old-refresh"]
    assert body["client_id"] == ["271296"]

    _assert_get(fake.calls[1], token="new-access")

    # The rotated refresh token was persisted back to the cache.
    saved = json.loads(env_and_cache.read_text())
    assert saved["refresh_token"] == "new-refresh"
    assert saved["access_token"] == "new-access"


def test_reactive_401_refreshes_and_retries(monkeypatch, capsys):
    responses = [
        http_error(401, {"message": "Authorization Error"}),
        TOKEN_PAYLOAD,
        {"id": 1, "firstname": "K"},
    ]
    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(mod, ["athlete"], monkeypatch)

    assert len(fake.calls) == 3
    assert fake.calls[0].method == "GET"          # first GET -> 401
    assert fake.calls[1].method == "POST"         # refresh
    _assert_get(fake.calls[2], token="new-access")  # retried GET
    assert "K" in capsys.readouterr().out


def test_refresh_http_error_exits(monkeypatch, env_and_cache):
    env_and_cache.write_text(
        json.dumps({"access_token": "o", "refresh_token": "r", "expires_at": 0})
    )
    patch_urlopen(monkeypatch, mod, [http_error(400, {"message": "bad"})])
    with pytest.raises(SystemExit):
        run_cli(mod, ["athlete"], monkeypatch)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_rate_limit_exits_with_note(monkeypatch):
    err = http_error(429, {"message": "Rate Limit Exceeded"})
    err.headers = {"X-RateLimit-Usage": "200,2000", "X-RateLimit-Limit": "200,2000"}
    patch_urlopen(monkeypatch, mod, [err])
    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["athlete"], monkeypatch)
    assert "rate limit" in str(exc.value).lower()


def test_generic_http_error_exits(monkeypatch):
    patch_urlopen(monkeypatch, mod, [http_error(404, {"message": "Not Found"})])
    with pytest.raises(SystemExit):
        run_cli(mod, ["activity", "999"], monkeypatch)


def test_missing_env_exits_before_network(monkeypatch, env_and_cache):
    # No cache file, and the seed env vars are gone -> exit before any HTTP.
    env_and_cache.unlink()
    monkeypatch.delenv("STRAVA_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("STRAVA_REFRESH_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        run_cli(mod, ["athlete"], monkeypatch)


# ---------------------------------------------------------------------------
# Athlete
# ---------------------------------------------------------------------------


def test_athlete(monkeypatch, capsys):
    fake = patch_urlopen(
        monkeypatch, mod, lambda req: {"id": 7, "firstname": "Kyle", "lastname": "P", "city": "Ottawa"}
    )
    run_cli(mod, ["athlete"], monkeypatch)
    out = capsys.readouterr().out
    assert "Kyle P" in out
    assert "id: 7" in out
    assert _path(fake.last_request).endswith("/athlete")


def test_athlete_zones(monkeypatch, capsys):
    payload = {"heart_rate": {"zones": [{"min": 0, "max": 100}, {"min": 100, "max": 200}]}}
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["athlete-zones"], monkeypatch)
    out = capsys.readouterr().out
    assert "Heart rate zones: 2" in out
    assert _path(fake.last_request).endswith("/athlete/zones")


def test_athlete_stats_resolves_id(monkeypatch, capsys):
    def responses(req):
        if _path(req).endswith("/athlete"):
            return {"id": 7}
        return {"recent_run_totals": {"count": 3, "distance": 30000}}

    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(mod, ["athlete-stats"], monkeypatch)
    out = capsys.readouterr().out
    assert "3 activities" in out
    assert "30.00 km" in out
    assert _path(fake.last_request).endswith("/athletes/7/stats")


def test_athlete_stats_explicit_id(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"all_run_totals": {"count": 1, "distance": 1000}})
    run_cli(mod, ["athlete-stats", "--id", "42"], monkeypatch)
    assert _path(fake.last_request).endswith("/athletes/42/stats")


def test_athlete_clubs(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: [{"id": 5, "name": "Runners", "member_count": 10}])
    run_cli(mod, ["athlete-clubs"], monkeypatch)
    out = capsys.readouterr().out
    assert "Runners" in out
    assert _path(fake.last_request).endswith("/athlete/clubs")


def test_athlete_routes(monkeypatch, capsys):
    def responses(req):
        if _path(req).endswith("/athlete"):
            return {"id": 7}
        return [{"id": 9, "name": "Loop", "distance": 5000}]

    fake = patch_urlopen(monkeypatch, mod, responses)
    run_cli(mod, ["athlete-routes"], monkeypatch)
    out = capsys.readouterr().out
    assert "Loop" in out
    assert _path(fake.last_request).endswith("/athletes/7/routes")


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


def test_activities_with_filters(monkeypatch, capsys):
    payload = [
        {"id": 1, "name": "Morning Run", "type": "Run", "distance": 10000,
         "moving_time": 3000, "start_date_local": "2026-01-02T08:00:00Z"}
    ]
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(
        mod,
        ["activities", "--after", "2026-01-01", "--per-page", "500", "--page", "2"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert "Morning Run" in out
    assert "10.00 km" in out
    qs = _qs(fake.last_request)
    assert qs["after"] == ["1767225600"]      # 2026-01-01 UTC epoch
    assert qs["per_page"] == ["200"]          # clamped
    assert qs["page"] == ["2"]
    assert "before" not in qs                  # None dropped


def test_activities_empty(monkeypatch, capsys):
    patch_urlopen(monkeypatch, mod, lambda req: [])
    run_cli(mod, ["activities"], monkeypatch)
    assert "No activities found." in capsys.readouterr().out


def test_activity(monkeypatch, capsys):
    payload = {
        "id": 55, "name": "Race", "type": "Run", "distance": 21097,
        "moving_time": 5400, "elapsed_time": 5500, "total_elevation_gain": 100,
        "start_date_local": "2026-03-01T09:00:00Z", "description": "PB!",
    }
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["activity", "55"], monkeypatch)
    out = capsys.readouterr().out
    assert "# Race  (id: 55)" in out
    assert "21.10 km" in out
    assert "1:30:00" in out
    assert "PB!" in out
    assert _path(fake.last_request).endswith("/activities/55")


def test_activity_comments(monkeypatch, capsys):
    payload = [{"created_at": "2026-01-01", "text": "nice", "athlete": {"firstname": "A", "lastname": "B"}}]
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["activity-comments", "55"], monkeypatch)
    out = capsys.readouterr().out
    assert "A B: nice" in out
    assert _path(fake.last_request).endswith("/activities/55/comments")


def test_activity_kudos(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: [{"firstname": "A", "lastname": "B"}])
    run_cli(mod, ["activity-kudos", "55"], monkeypatch)
    assert "A B" in capsys.readouterr().out
    assert _path(fake.last_request).endswith("/activities/55/kudos")


def test_activity_laps(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: [{"lap_index": 1, "distance": 1000, "moving_time": 300}])
    run_cli(mod, ["activity-laps", "55"], monkeypatch)
    out = capsys.readouterr().out
    assert "Lap 1" in out
    assert _path(fake.last_request).endswith("/activities/55/laps")


def test_activity_zones(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: [{"type": "heartrate", "distribution_buckets": [1, 2, 3]}])
    run_cli(mod, ["activity-zones", "55"], monkeypatch)
    out = capsys.readouterr().out
    assert "heartrate: 3 buckets" in out
    assert _path(fake.last_request).endswith("/activities/55/zones")


def test_activity_streams_summary(monkeypatch, capsys):
    payload = {"time": {"data": [0, 1, 2]}, "heartrate": {"data": [100, 110]}}
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["activity-streams", "55", "--keys", "time,heartrate"], monkeypatch)
    out = capsys.readouterr().out
    assert "time: 3 points" in out
    assert "heartrate: 2 points" in out
    qs = _qs(fake.last_request)
    assert qs["keys"] == ["time,heartrate"]
    assert qs["key_by_type"] == ["true"]
    assert _path(fake.last_request).endswith("/activities/55/streams")


def test_activity_streams_raw(monkeypatch, capsys):
    payload = {"time": {"data": [0, 1, 2]}}
    patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["activity-streams", "55", "--raw"], monkeypatch)
    out = capsys.readouterr().out
    assert '"data"' in out          # raw JSON, not the summary
    assert "points" not in out


# ---------------------------------------------------------------------------
# Clubs
# ---------------------------------------------------------------------------


def test_club(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"id": 3, "name": "TeamX", "member_count": 50})
    run_cli(mod, ["club", "3"], monkeypatch)
    out = capsys.readouterr().out
    assert "TeamX" in out
    assert _path(fake.last_request).endswith("/clubs/3")


def test_club_activities(monkeypatch, capsys):
    payload = [{"athlete": {"firstname": "A", "lastname": "B"}, "type": "Ride", "distance": 20000, "name": "Spin"}]
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["club-activities", "3"], monkeypatch)
    out = capsys.readouterr().out
    assert "Spin" in out
    assert _path(fake.last_request).endswith("/clubs/3/activities")


def test_club_members(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: [{"firstname": "A", "lastname": "B", "admin": True}])
    run_cli(mod, ["club-members", "3"], monkeypatch)
    out = capsys.readouterr().out
    assert "A B (admin)" in out
    assert _path(fake.last_request).endswith("/clubs/3/members")


def test_club_admins(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: [{"firstname": "A", "lastname": "B"}])
    run_cli(mod, ["club-admins", "3"], monkeypatch)
    assert "A B" in capsys.readouterr().out
    assert _path(fake.last_request).endswith("/clubs/3/admins")


# ---------------------------------------------------------------------------
# Gear
# ---------------------------------------------------------------------------


def test_gear(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"id": "b1", "name": "Bike", "brand_name": "Trek", "distance": 100000})
    run_cli(mod, ["gear", "b1"], monkeypatch)
    out = capsys.readouterr().out
    assert "Bike" in out
    assert "Trek" in out
    assert "100.00 km" in out
    assert _path(fake.last_request).endswith("/gears/b1")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_route(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"id": 9, "name": "Loop", "distance": 5000, "elevation_gain": 50})
    run_cli(mod, ["route", "9"], monkeypatch)
    out = capsys.readouterr().out
    assert "Loop" in out
    assert _path(fake.last_request).endswith("/routes/9")


def test_route_export_gpx(monkeypatch, capsys):
    from conftest import FakeResponse

    xml = "<gpx>...</gpx>"
    fake = patch_urlopen(monkeypatch, mod, [FakeResponse(xml.encode("utf-8"))])
    run_cli(mod, ["route-export", "9", "--format", "gpx"], monkeypatch)
    out = capsys.readouterr().out
    assert "<gpx>" in out
    assert _path(fake.last_request).endswith("/routes/9/gpx")


def test_route_streams(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"distance": {"data": [0, 1]}})
    run_cli(mod, ["route-streams", "9"], monkeypatch)
    out = capsys.readouterr().out
    assert "distance: 2 points" in out
    assert _path(fake.last_request).endswith("/routes/9/streams")


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------


def test_segment(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"id": 11, "name": "Hill", "distance": 800, "average_grade": 8.0, "climb_category": 2})
    run_cli(mod, ["segment", "11"], monkeypatch)
    out = capsys.readouterr().out
    assert "Hill" in out
    assert _path(fake.last_request).endswith("/segments/11")


def test_segments_starred(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: [{"id": 11, "name": "Hill", "distance": 800, "average_grade": 8.0}])
    run_cli(mod, ["segments-starred"], monkeypatch)
    out = capsys.readouterr().out
    assert "Hill" in out
    assert _path(fake.last_request).endswith("/segments/starred")


def test_segments_explore(monkeypatch, capsys):
    payload = {"segments": [{"id": 11, "name": "Hill", "distance": 800, "climb_category": 2}]}
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(
        mod,
        ["segments-explore", "--bounds", "1,2,3,4", "--activity-type", "riding"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert "Hill" in out
    qs = _qs(fake.last_request)
    assert qs["bounds"] == ["1,2,3,4"]
    assert qs["activity_type"] == ["riding"]
    assert _path(fake.last_request).endswith("/segments/explore")


def test_segments_explore_bad_bounds_exits(monkeypatch):
    patch_urlopen(monkeypatch, mod, lambda req: {})
    with pytest.raises(SystemExit):
        run_cli(mod, ["segments-explore", "--bounds", "1,2,3"], monkeypatch)


def test_segment_streams(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"latlng": {"data": [[0, 0], [1, 1]]}})
    run_cli(mod, ["segment-streams", "11"], monkeypatch)
    out = capsys.readouterr().out
    assert "latlng: 2 points" in out
    assert _path(fake.last_request).endswith("/segments/11/streams")


# ---------------------------------------------------------------------------
# Segment efforts
# ---------------------------------------------------------------------------


def test_segment_efforts_all(monkeypatch, capsys):
    payload = [{"id": 100, "start_date_local": "2026-01-01T00:00:00Z", "elapsed_time": 200, "athlete": {"id": 7}}]
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["segment-efforts", "11"], monkeypatch)
    out = capsys.readouterr().out
    assert "3:20" in out
    assert _path(fake.last_request).endswith("/segments/11/all_efforts")


def test_segment_efforts_athlete(monkeypatch, capsys):
    payload = [{"id": 100, "start_date_local": "2026-01-01T00:00:00Z", "elapsed_time": 200, "athlete": {"id": 7}}]
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["segment-efforts", "11", "--athlete-effort"], monkeypatch)
    qs = _qs(fake.last_request)
    assert _path(fake.last_request).endswith("/segment_efforts")
    assert qs["segment_id"] == ["11"]


def test_segment_effort(monkeypatch, capsys):
    payload = {"id": 100, "segment": {"name": "Hill"}, "start_date_local": "2026-01-01", "elapsed_time": 200, "moving_time": 190, "distance": 800}
    fake = patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["segment-effort", "100"], monkeypatch)
    out = capsys.readouterr().out
    assert "Effort 100 on Hill" in out
    assert _path(fake.last_request).endswith("/segment_efforts/100")


def test_segment_effort_streams(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"time": {"data": [0, 1, 2]}})
    run_cli(mod, ["segment-effort-streams", "100"], monkeypatch)
    out = capsys.readouterr().out
    assert "time: 3 points" in out
    assert _path(fake.last_request).endswith("/segment_efforts/100/streams")


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------


def test_upload(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, lambda req: {"id": 500, "status": "Your activity is ready.", "activity_id": 999})
    run_cli(mod, ["upload", "500"], monkeypatch)
    out = capsys.readouterr().out
    assert "Upload 500" in out
    assert "999" in out
    assert _path(fake.last_request).endswith("/uploads/500")


# ---------------------------------------------------------------------------
# --json passthrough
# ---------------------------------------------------------------------------


def test_json_flag_passthrough(monkeypatch, capsys):
    payload = {"id": 7, "firstname": "Kyle"}
    patch_urlopen(monkeypatch, mod, lambda req: payload)
    run_cli(mod, ["athlete", "--json"], monkeypatch)
    out = capsys.readouterr().out
    assert json.loads(out) == payload
