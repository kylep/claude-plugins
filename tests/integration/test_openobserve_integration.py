import pytest

from conftest import http_error, load_script, patch_urlopen, run_cli

mod = load_script("openobserve")
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("O2_URL", "https://o2.test")
    monkeypatch.setenv("O2_TOKEN", "test-token")
    monkeypatch.setenv("O2_ORG", "default")


# Deterministic "now": every command computes now via time.time().
FIXED_NOW_S = 1_700_000_000
FIXED_NOW_US = FIXED_NOW_S * 1_000_000


@pytest.fixture(autouse=True)
def frozen_time(monkeypatch):
    monkeypatch.setattr(mod.time, "time", lambda: float(FIXED_NOW_S))


# ---------------------------------------------------------------------------
# Canned payloads
# ---------------------------------------------------------------------------

SEARCH_HITS = {
    "took": 12,
    "total": 2,
    "hits": [
        {"_timestamp": 1700000000000000, "message": "boom", "k8s_namespace": "prod"},
        {"_timestamp": 1700000001000000, "message": "bang", "k8s_namespace": "prod"},
    ],
}

EMPTY_SEARCH = {"took": 3, "total": 0, "hits": []}

ERROR_SUMMARY_HITS = {
    "took": 5,
    "total": 1,
    "hits": [
        {
            "log_level": "ERROR",
            "k8s_namespace": "prod",
            "k8s_pod": "api-7d9",
            "count": 9,
        }
    ],
}

RECENT_ERRORS_HITS = {
    "hits": [
        {
            "_timestamp": 1700000000000000,
            "k8s_namespace": "prod",
            "k8s_pod": "api-7d9",
            "k8s_container": "api",
            "message": "x" * 400,  # exercise the 300-char truncation
        }
    ]
}

STREAMS = {
    "list": [
        {
            "name": "k8s_logs",
            "stream_type": "logs",
            "stats": {"doc_num": 42, "storage_size": 1.5},
        }
    ]
}

STREAMS_WITH_SCHEMA = {
    "list": [
        {
            "name": "k8s_logs",
            "stream_type": "logs",
            "schema": [
                {"name": "message", "type": "Utf8"},
                {"name": "_timestamp", "type": "Int64"},
            ],
        }
    ]
}

ALERTS = {
    "list": [
        {"id": "a1", "name": "High errors", "enabled": True},
        {"id": "a2", "name": "Disk", "enabled": False},
    ]
}

ALERT_DETAIL = {"id": "a1", "name": "High errors", "enabled": True, "threshold": 5}


# ---------------------------------------------------------------------------
# search-logs
# ---------------------------------------------------------------------------


def test_search_logs(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [SEARCH_HITS])
    run_cli(mod, ["search-logs", "SELECT * FROM k8s_logs", "--limit", "100"], monkeypatch)

    out = capsys.readouterr().out
    assert "Query took 12ms. 2 total matches, returning 2." in out
    assert '"message": "boom"' in out

    req = fake.last_request
    assert req.full_url == "https://o2.test/api/default/_search"
    assert req.get_header("Authorization") == "Basic test-token"
    assert req.method == "POST"
    body = fake.request_body()
    assert body["query"]["sql"] == "SELECT * FROM k8s_logs"
    assert body["query"]["size"] == 100
    # end == "now" -> the frozen now in micros; start defaults to 1h ago.
    assert body["query"]["end_time"] == FIXED_NOW_US
    assert body["query"]["start_time"] == FIXED_NOW_US - 3600 * 1_000_000


def test_search_logs_explicit_range(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [SEARCH_HITS])
    run_cli(
        mod,
        ["search-logs", "SELECT 1", "--start", "15m", "--end", "5m"],
        monkeypatch,
    )
    body = fake.request_body()
    assert body["query"]["start_time"] == FIXED_NOW_US - 15 * 60 * 1_000_000
    assert body["query"]["end_time"] == FIXED_NOW_US - 5 * 60 * 1_000_000


def test_search_logs_no_results(monkeypatch, capsys):
    patch_urlopen(monkeypatch, mod, [EMPTY_SEARCH])
    run_cli(mod, ["search-logs", "SELECT 1"], monkeypatch)
    out = capsys.readouterr().out
    assert "0 total matches, returning 0." in out


# ---------------------------------------------------------------------------
# error-summary
# ---------------------------------------------------------------------------


def test_error_summary(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [ERROR_SUMMARY_HITS])
    run_cli(mod, ["error-summary", "--period", "2h"], monkeypatch)

    out = capsys.readouterr().out
    assert "Error/warning summary for the last 2h:" in out
    assert "ERROR" in out
    assert "api-7d9" in out

    body = fake.request_body()
    assert "GROUP BY log_level, k8s_namespace, k8s_pod" in body["query"]["sql"]
    assert "FROM k8s_logs" in body["query"]["sql"]
    assert body["query"]["end_time"] == FIXED_NOW_US
    assert body["query"]["start_time"] == FIXED_NOW_US - 2 * 3600 * 1_000_000


def test_error_summary_no_results(monkeypatch, capsys):
    patch_urlopen(monkeypatch, mod, [EMPTY_SEARCH])
    run_cli(mod, ["error-summary"], monkeypatch)
    out = capsys.readouterr().out
    assert "No errors or warnings in the last 1h." in out


# ---------------------------------------------------------------------------
# recent-errors
# ---------------------------------------------------------------------------


def test_recent_errors(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [RECENT_ERRORS_HITS])
    run_cli(mod, ["recent-errors", "--limit", "20"], monkeypatch)

    out = capsys.readouterr().out
    assert "1 recent errors (last 1h):" in out
    assert "prod/api-7d9" in out
    assert "..." in out  # truncated message

    body = fake.request_body()
    sql = body["query"]["sql"]
    assert "ORDER BY _timestamp DESC LIMIT 20" in sql
    assert "k8s_namespace =" not in sql  # no namespace filter by default


def test_recent_errors_namespace_filter_and_escape(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [RECENT_ERRORS_HITS])
    run_cli(
        mod,
        ["recent-errors", "--namespace", "pr'od"],
        monkeypatch,
    )
    sql = fake.request_body()["query"]["sql"]
    # Single quote doubled for SQL literal escaping.
    assert "k8s_namespace = 'pr''od'" in sql


def test_recent_errors_no_results(monkeypatch, capsys):
    patch_urlopen(monkeypatch, mod, [{"hits": []}])
    run_cli(mod, ["recent-errors"], monkeypatch)
    out = capsys.readouterr().out
    assert "No errors in the last 1h." in out


# ---------------------------------------------------------------------------
# list-streams
# ---------------------------------------------------------------------------


def test_list_streams(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [STREAMS])
    run_cli(mod, ["list-streams", "--type", "logs"], monkeypatch)

    out = capsys.readouterr().out
    assert "k8s_logs" in out
    assert "42" in out

    req = fake.last_request
    assert req.full_url == "https://o2.test/api/default/streams?type=logs"
    assert req.get_header("Authorization") == "Basic test-token"
    assert req.method == "GET"


def test_list_streams_no_type(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [STREAMS])
    run_cli(mod, ["list-streams"], monkeypatch)
    req = fake.last_request
    assert req.full_url == "https://o2.test/api/default/streams"  # no query string


def test_list_streams_no_results(monkeypatch, capsys):
    patch_urlopen(monkeypatch, mod, [{"list": []}])
    run_cli(mod, ["list-streams"], monkeypatch)
    assert "No streams found." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# stream-schema
# ---------------------------------------------------------------------------


def test_stream_schema(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [STREAMS_WITH_SCHEMA])
    run_cli(mod, ["stream-schema", "--stream", "k8s_logs"], monkeypatch)

    out = capsys.readouterr().out
    assert "Schema for 'k8s_logs' (2 fields):" in out
    assert "message" in out
    assert "Utf8" in out

    req = fake.last_request
    assert "type=logs" in req.full_url
    assert "fetchSchema=true" in req.full_url


def test_stream_schema_not_found_exits(monkeypatch):
    patch_urlopen(monkeypatch, mod, [{"list": []}])
    with pytest.raises(SystemExit):
        run_cli(mod, ["stream-schema", "--stream", "nope"], monkeypatch)


def test_stream_schema_empty_schema(monkeypatch, capsys):
    payload = {"list": [{"name": "k8s_logs", "schema": []}]}
    patch_urlopen(monkeypatch, mod, [payload])
    run_cli(mod, ["stream-schema", "--stream", "k8s_logs"], monkeypatch)
    assert "No schema available for 'k8s_logs'." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# list-alerts
# ---------------------------------------------------------------------------


def test_list_alerts(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [ALERTS])
    run_cli(mod, ["list-alerts"], monkeypatch)

    out = capsys.readouterr().out
    assert "2 alerts:" in out
    assert "[a1] High errors (enabled)" in out
    assert "[a2] Disk (disabled)" in out

    req = fake.last_request
    assert req.full_url == "https://o2.test/api/v2/default/alerts"
    assert req.method == "GET"


def test_list_alerts_no_results(monkeypatch, capsys):
    patch_urlopen(monkeypatch, mod, [{"list": []}])
    run_cli(mod, ["list-alerts"], monkeypatch)
    assert "No alerts configured." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# get-alert
# ---------------------------------------------------------------------------


def test_get_alert(monkeypatch, capsys):
    fake = patch_urlopen(monkeypatch, mod, [ALERT_DETAIL])
    run_cli(mod, ["get-alert", "a1"], monkeypatch)

    out = capsys.readouterr().out
    assert '"id": "a1"' in out
    assert '"threshold": 5' in out

    req = fake.last_request
    assert req.full_url == "https://o2.test/api/v2/default/alerts/a1"
    assert req.method == "GET"


# ---------------------------------------------------------------------------
# org appears in URL; error and missing-env handling
# ---------------------------------------------------------------------------


def test_org_appears_in_url(monkeypatch, capsys):
    monkeypatch.setenv("O2_ORG", "acme")
    fake = patch_urlopen(monkeypatch, mod, [STREAMS])
    run_cli(mod, ["list-streams"], monkeypatch)
    assert "/api/acme/streams" in fake.last_request.full_url


def test_http_error_exits(monkeypatch):
    patch_urlopen(monkeypatch, mod, [http_error(500, {"error": "boom"})])
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-streams"], monkeypatch)


def test_search_http_error_exits(monkeypatch):
    patch_urlopen(monkeypatch, mod, [http_error(400, "bad sql")])
    with pytest.raises(SystemExit):
        run_cli(mod, ["search-logs", "SELECT 1"], monkeypatch)


def test_missing_url_exits_before_network(monkeypatch):
    monkeypatch.delenv("O2_URL", raising=False)
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-streams"], monkeypatch)


def test_missing_token_exits_before_network(monkeypatch):
    monkeypatch.delenv("O2_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        run_cli(mod, ["list-streams"], monkeypatch)
