"""Integration tests for gsc.py.

The google client libraries are NOT installed in this environment. The script
imports them lazily *inside* get_service(), so we inject fake modules into
sys.modules right before invoking the CLI. Each fake module is registered with
monkeypatch.setitem so it is torn down per-test.

We provide:
  * a fake Credentials (valid, not expired) loaded from an on-disk token.json,
  * a fake discovery.build(...) returning a service whose
    searchanalytics().query(...).execute() (and the sitemaps / urlInspection
    equivalents) return canned payloads, capturing the args passed in.
"""

import json
import types

import pytest

from conftest import load_script, run_cli

mod = load_script("gsc")
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fake google service plumbing
# ---------------------------------------------------------------------------


class _Recorder:
    """Captures the kwargs/body the script passes to each API method."""

    def __init__(self):
        self.calls = {}


class _Method:
    def __init__(self, recorder, name, payload):
        self._rec = recorder
        self._name = name
        self._payload = payload

    def __call__(self, **kwargs):
        self._rec.calls[self._name] = kwargs
        return self

    def execute(self):
        return self._payload


class _SearchAnalytics:
    def __init__(self, recorder, payload):
        self._rec = recorder
        self._payload = payload

    def query(self, **kwargs):
        self._rec.calls["query"] = kwargs
        return _Method(self._rec, "query_execute", self._payload)


class _Sitemaps:
    def __init__(self, recorder, list_payload):
        self._rec = recorder
        self._list_payload = list_payload

    def list(self, **kwargs):
        self._rec.calls["sitemaps_list"] = kwargs
        return _Method(self._rec, "sitemaps_list_execute", self._list_payload)

    def submit(self, **kwargs):
        self._rec.calls["sitemaps_submit"] = kwargs
        return _Method(self._rec, "sitemaps_submit_execute", {})


class _UrlInspectionIndex:
    def __init__(self, recorder, payload):
        self._rec = recorder
        self._payload = payload

    def inspect(self, **kwargs):
        self._rec.calls["inspect"] = kwargs
        return _Method(self._rec, "inspect_execute", self._payload)


class _UrlInspection:
    def __init__(self, recorder, payload):
        self._rec = recorder
        self._payload = payload

    def index(self):
        return _UrlInspectionIndex(self._rec, self._payload)


class FakeService:
    def __init__(self, recorder, payloads):
        self._rec = recorder
        self._payloads = payloads

    def searchanalytics(self):
        return _SearchAnalytics(self._rec, self._payloads.get("query", {"rows": []}))

    def sitemaps(self):
        return _Sitemaps(self._rec, self._payloads.get("sitemaps", {}))

    def urlInspection(self):
        return _UrlInspection(self._rec, self._payloads.get("inspect", {}))


class FakeCredentials:
    """Stand-in for google.oauth2.credentials.Credentials: valid + not expired."""

    valid = True
    expired = False
    refresh_token = "refresh-xyz"

    @classmethod
    def from_authorized_user_file(cls, path, scopes):
        return cls()

    def refresh(self, request):  # pragma: no cover - not exercised when valid
        raise AssertionError("refresh() should not be called for a valid credential")

    def to_json(self):  # pragma: no cover - only used on the write_token path
        return json.dumps({"refresh_token": self.refresh_token})


def _install_fake_google(monkeypatch, recorder, payloads):
    """Register fake google.* modules in sys.modules (torn down per test)."""
    build_calls = {}

    def fake_build(service, version, credentials=None, cache_discovery=None):
        build_calls["args"] = (service, version)
        build_calls["credentials"] = credentials
        build_calls["cache_discovery"] = cache_discovery
        return FakeService(recorder, payloads)

    # google / google.oauth2 / google.oauth2.credentials
    google = types.ModuleType("google")
    oauth2 = types.ModuleType("google.oauth2")
    credentials_mod = types.ModuleType("google.oauth2.credentials")
    credentials_mod.Credentials = FakeCredentials

    # google.auth / google.auth.transport / google.auth.transport.requests
    auth = types.ModuleType("google.auth")
    transport = types.ModuleType("google.auth.transport")
    requests_mod = types.ModuleType("google.auth.transport.requests")
    requests_mod.Request = lambda: object()

    # google_auth_oauthlib / google_auth_oauthlib.flow
    oauthlib = types.ModuleType("google_auth_oauthlib")
    flow_mod = types.ModuleType("google_auth_oauthlib.flow")

    class _Flow:
        @classmethod
        def from_client_secrets_file(cls, path, scopes):  # pragma: no cover
            raise AssertionError("OAuth flow should not run with a valid token")

    flow_mod.InstalledAppFlow = _Flow

    # googleapiclient / googleapiclient.discovery
    apiclient = types.ModuleType("googleapiclient")
    discovery_mod = types.ModuleType("googleapiclient.discovery")
    discovery_mod.build = fake_build

    for name, module in {
        "google": google,
        "google.oauth2": oauth2,
        "google.oauth2.credentials": credentials_mod,
        "google.auth": auth,
        "google.auth.transport": transport,
        "google.auth.transport.requests": requests_mod,
        "google_auth_oauthlib": oauthlib,
        "google_auth_oauthlib.flow": flow_mod,
        "googleapiclient": apiclient,
        "googleapiclient.discovery": discovery_mod,
    }.items():
        monkeypatch.setitem(__import__("sys").modules, name, module)

    return build_calls


@pytest.fixture
def gsc_env(monkeypatch, tmp_path):
    """Lay down a token.json and point the module constants at it.

    The script reads TOKEN_PATH / CLIENT_SECRETS / SITE_URL_ENV as module-level
    Path/str constants computed at import time, so we patch the constants
    directly (the module is import-cached across the suite).
    """
    token = tmp_path / "token.json"
    token.write_text(json.dumps({"refresh_token": "refresh-xyz"}), encoding="utf-8")
    secrets = tmp_path / "client_secrets.json"
    secrets.write_text(json.dumps({"installed": {}}), encoding="utf-8")

    monkeypatch.setenv("GSC_TOKEN_PATH", str(token))
    monkeypatch.setenv("GSC_CLIENT_SECRETS", str(secrets))
    monkeypatch.setenv("GSC_SITE_URL", "https://kyle.example/")

    monkeypatch.setattr(mod, "TOKEN_PATH", token)
    monkeypatch.setattr(mod, "CLIENT_SECRETS", secrets)
    monkeypatch.setattr(mod, "SITE_URL_ENV", "https://kyle.example/")
    return tmp_path


def _setup(monkeypatch, gsc_env, payloads):
    recorder = _Recorder()
    build_calls = _install_fake_google(monkeypatch, recorder, payloads)
    return recorder, build_calls


# ---------------------------------------------------------------------------
# search-analytics
# ---------------------------------------------------------------------------


def test_search_analytics_renders_and_builds_query(monkeypatch, capsys, gsc_env):
    payload = {
        "rows": [
            {
                "keys": ["claude code"],
                "clicks": 42,
                "impressions": 900,
                "ctr": 0.0467,
                "position": 3.1,
            },
            {
                "keys": ["pai tools"],
                "clicks": 5,
                "impressions": 120,
                "ctr": 0.0417,
                "position": 8.9,
            },
        ]
    }
    recorder, build_calls = _setup(monkeypatch, gsc_env, {"query": payload})

    run_cli(
        mod,
        ["search-analytics", "--start", "2026-01-01", "--end", "2026-01-31",
         "--dimensions", "query,page", "--limit", "10"],
        monkeypatch,
    )

    out = capsys.readouterr().out
    assert "Search analytics for https://kyle.example/ (2026-01-01 to 2026-01-31), 2 rows:" in out
    assert "claude code" in out
    assert "pai tools" in out
    assert "Query" in out and "Page" in out

    # The fake discovery.build was invoked for the search console service.
    assert build_calls["args"] == ("searchconsole", "v1")
    assert isinstance(build_calls["credentials"], FakeCredentials)

    # The query was built with the expected site url / date range / dimensions.
    q = recorder.calls["query"]
    assert q["siteUrl"] == "https://kyle.example/"
    assert q["body"]["startDate"] == "2026-01-01"
    assert q["body"]["endDate"] == "2026-01-31"
    assert q["body"]["dimensions"] == ["query", "page"]
    assert q["body"]["rowLimit"] == 10


def test_search_analytics_site_flag_overrides_env(monkeypatch, capsys, gsc_env):
    recorder, _ = _setup(monkeypatch, gsc_env, {"query": {"rows": []}})
    run_cli(
        mod,
        ["search-analytics", "--site", "https://other.example/"],
        monkeypatch,
    )
    assert recorder.calls["query"]["siteUrl"] == "https://other.example/"


def test_search_analytics_empty_rows_message(monkeypatch, capsys, gsc_env):
    _setup(monkeypatch, gsc_env, {"query": {"rows": []}})
    run_cli(
        mod,
        ["search-analytics", "--start", "2026-02-01", "--end", "2026-02-10"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert "No search analytics data for 2026-02-01 to 2026-02-10." in out


def test_search_analytics_filters_passed_through(monkeypatch, capsys, gsc_env):
    recorder, _ = _setup(monkeypatch, gsc_env, {"query": {"rows": []}})
    run_cli(
        mod,
        ["search-analytics", "--page-filter", "/blog", "--query-filter", "claude"],
        monkeypatch,
    )
    body = recorder.calls["query"]["body"]
    filters = body["dimensionFilterGroups"][0]["filters"]
    assert {"dimension": "page", "operator": "contains", "expression": "/blog"} in filters
    assert {"dimension": "query", "operator": "contains", "expression": "claude"} in filters


# ---------------------------------------------------------------------------
# inspect-url
# ---------------------------------------------------------------------------


def test_inspect_url_renders_index_status(monkeypatch, capsys, gsc_env):
    payload = {
        "inspectionResult": {
            "indexStatusResult": {
                "verdict": "PASS",
                "coverageState": "Submitted and indexed",
                "indexingState": "INDEXING_ALLOWED",
                "pageFetchState": "SUCCESSFUL",
                "robotsTxtState": "ALLOWED",
                "lastCrawlTime": "2026-06-01T12:00:00Z",
                "crawledAs": "MOBILE",
                "googleCanonical": "https://kyle.example/page",
                "userCanonical": "https://kyle.example/page",
                "referringUrls": ["https://a.example", "https://b.example"],
            },
            "richResultsResult": {
                "verdict": "PASS",
                "detectedItems": [
                    {
                        "richResultType": "Article",
                        "items": [
                            {"issues": [{"issueMessage": "Missing author", "severity": "WARNING"}]}
                        ],
                    }
                ],
            },
        }
    }
    recorder, _ = _setup(monkeypatch, gsc_env, {"inspect": payload})

    run_cli(
        mod,
        ["inspect-url", "https://kyle.example/page"],
        monkeypatch,
    )

    out = capsys.readouterr().out
    assert "URL Inspection: https://kyle.example/page" in out
    assert "Verdict:        PASS" in out
    assert "Submitted and indexed" in out
    assert "Referring URLs: https://a.example, https://b.example" in out
    assert "## Rich Results" in out
    assert "- Article" in out
    assert "Issue: Missing author (WARNING)" in out

    body = recorder.calls["inspect"]["body"]
    assert body == {
        "inspectionUrl": "https://kyle.example/page",
        "siteUrl": "https://kyle.example/",
    }


def test_inspect_url_handles_missing_fields(monkeypatch, capsys, gsc_env):
    _setup(monkeypatch, gsc_env, {"inspect": {}})
    run_cli(mod, ["inspect-url", "https://kyle.example/x"], monkeypatch)
    out = capsys.readouterr().out
    assert "Verdict:        UNKNOWN" in out
    assert "Coverage:       N/A" in out


# ---------------------------------------------------------------------------
# list-sitemaps
# ---------------------------------------------------------------------------


def test_list_sitemaps_renders_rows(monkeypatch, capsys, gsc_env):
    payload = {
        "sitemap": [
            {
                "path": "https://kyle.example/sitemap.xml",
                "type": "sitemap",
                "lastSubmitted": "2026-05-30T08:00:00Z",
                "errors": 0,
                "warnings": 2,
                "contents": [
                    {"type": "web", "submitted": 120, "indexed": 118},
                ],
            }
        ]
    }
    recorder, _ = _setup(monkeypatch, gsc_env, {"sitemaps": payload})

    run_cli(mod, ["list-sitemaps"], monkeypatch)

    out = capsys.readouterr().out
    assert "Sitemaps for https://kyle.example/:" in out
    assert "https://kyle.example/sitemap.xml" in out
    assert "2026-05-30" in out  # truncated to first 10 chars
    assert "web: 120 submitted, 118 indexed" in out
    assert recorder.calls["sitemaps_list"]["siteUrl"] == "https://kyle.example/"


def test_list_sitemaps_empty(monkeypatch, capsys, gsc_env):
    _setup(monkeypatch, gsc_env, {"sitemaps": {"sitemap": []}})
    run_cli(mod, ["list-sitemaps"], monkeypatch)
    out = capsys.readouterr().out
    assert "No sitemaps found for https://kyle.example/." in out


# ---------------------------------------------------------------------------
# submit-sitemap
# ---------------------------------------------------------------------------


def test_submit_sitemap(monkeypatch, capsys, gsc_env):
    recorder, _ = _setup(monkeypatch, gsc_env, {})
    run_cli(
        mod,
        ["submit-sitemap", "https://kyle.example/sitemap.xml"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert "Sitemap submitted: https://kyle.example/sitemap.xml" in out
    call = recorder.calls["sitemaps_submit"]
    assert call["siteUrl"] == "https://kyle.example/"
    assert call["feedpath"] == "https://kyle.example/sitemap.xml"


# ---------------------------------------------------------------------------
# Credential loading path
# ---------------------------------------------------------------------------


def test_missing_token_and_secrets_exits(monkeypatch, capsys, tmp_path):
    """No token.json and no client_secrets.json -> OAuth setup error, no flow."""
    recorder = _Recorder()
    _install_fake_google(monkeypatch, recorder, {"query": {"rows": []}})

    missing_token = tmp_path / "nope-token.json"
    missing_secrets = tmp_path / "nope-secrets.json"
    monkeypatch.setattr(mod, "TOKEN_PATH", missing_token)
    monkeypatch.setattr(mod, "CLIENT_SECRETS", missing_secrets)
    monkeypatch.setattr(mod, "SITE_URL_ENV", "https://kyle.example/")

    with pytest.raises(SystemExit) as exc:
        run_cli(mod, ["search-analytics"], monkeypatch)
    assert "OAuth client secrets not found" in str(exc.value)
