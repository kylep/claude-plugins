from urllib.parse import parse_qs, urlparse

import pytest

from conftest import http_error, load_script, patch_urlopen, run_cli

mod = load_script("google_news")
pytestmark = pytest.mark.integration


def _articles(n):
    return [
        {
            "title": f"Headline {i}",
            "description": f"Description {i}",
            "source": {"name": f"Source {i}"},
            "url": f"https://news.example/{i}",
            "publishedAt": "2026-06-05T12:00:00Z",
            "content": f"Full content for article {i}",
        }
        for i in range(n)
    ]


def _query(url):
    """Parse the query string of a recorded request URL into a flat dict.

    The script calls urlopen(url, ...) with a plain string, so FakeUrlopen
    records the URL string itself (not a Request object).
    """
    qs = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in qs.items()}


# --------------------------------------------------------------------------- #
# search subcommand
# --------------------------------------------------------------------------- #


def test_search_renders_and_builds_request(monkeypatch, capsys):
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")
    payload = {"totalArticles": 2, "articles": _articles(2)}
    fake = patch_urlopen(monkeypatch, mod, [payload])
    run_cli(mod, ["search", "AI agents"], monkeypatch)

    out = capsys.readouterr().out
    assert 'Found 2 articles for "AI agents":' in out
    assert '<news-data source="gnews-api">' in out
    assert "1. **Headline 0**" in out
    assert "2. **Headline 1**" in out

    url = fake.last_request
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "gnews.io"
    assert parsed.path == "/api/v4/search"
    params = _query(url)
    assert params["q"] == "AI agents"
    assert params["lang"] == "en"
    assert params["max"] == "10"
    assert params["apikey"] == "test-key"
    assert "from" not in params
    assert "to" not in params


def test_search_passes_optional_flags(monkeypatch, capsys):
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")
    fake = patch_urlopen(monkeypatch, mod, [{"totalArticles": 0, "articles": []}])
    run_cli(
        mod,
        [
            "search",
            "rust lang",
            "--max",
            "5",
            "--lang",
            "fr",
            "--from",
            "2026-03-14T00:00:00Z",
            "--to",
            "2026-04-01T00:00:00Z",
        ],
        monkeypatch,
    )
    params = _query(fake.last_request)
    assert params["q"] == "rust lang"
    assert params["max"] == "5"
    assert params["lang"] == "fr"
    assert params["from"] == "2026-03-14T00:00:00Z"
    assert params["to"] == "2026-04-01T00:00:00Z"
    assert params["apikey"] == "test-key"


def test_search_no_results(monkeypatch, capsys):
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")
    patch_urlopen(monkeypatch, mod, [{"totalArticles": 0, "articles": []}])
    run_cli(mod, ["search", "nothingmatches"], monkeypatch)

    out = capsys.readouterr().out
    assert 'Found 0 articles for "nothingmatches":' in out
    assert "No articles found." in out


def test_search_http_error_exits(monkeypatch):
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")
    patch_urlopen(monkeypatch, mod, [http_error(403, {"errors": ["forbidden"]})])
    with pytest.raises(SystemExit):
        run_cli(mod, ["search", "AI"], monkeypatch)


# --------------------------------------------------------------------------- #
# headlines subcommand
# --------------------------------------------------------------------------- #


def test_headlines_default_category(monkeypatch, capsys):
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")
    payload = {"totalArticles": 1, "articles": _articles(1)}
    fake = patch_urlopen(monkeypatch, mod, [payload])
    run_cli(mod, ["headlines"], monkeypatch)

    out = capsys.readouterr().out
    assert "Top technology headlines:" in out
    assert "1. **Headline 0**" in out

    url = fake.last_request
    assert urlparse(url).path == "/api/v4/top-headlines"
    params = _query(url)
    assert params["category"] == "technology"
    assert params["lang"] == "en"
    assert params["max"] == "10"
    assert params["apikey"] == "test-key"


def test_headlines_custom_category_and_flags(monkeypatch, capsys):
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")
    fake = patch_urlopen(monkeypatch, mod, [{"totalArticles": 0, "articles": []}])
    run_cli(
        mod,
        ["headlines", "--category", "science", "--max", "3", "--lang", "de"],
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert "Top science headlines:" in out

    params = _query(fake.last_request)
    assert params["category"] == "science"
    assert params["max"] == "3"
    assert params["lang"] == "de"


def test_headlines_no_results(monkeypatch, capsys):
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")
    patch_urlopen(monkeypatch, mod, [{"totalArticles": 0, "articles": []}])
    run_cli(mod, ["headlines"], monkeypatch)

    out = capsys.readouterr().out
    assert "No articles found." in out


def test_headlines_http_error_exits(monkeypatch):
    monkeypatch.setenv("GNEWS_API_KEY", "test-key")
    patch_urlopen(monkeypatch, mod, [http_error(401, {"errors": ["bad key"]})])
    with pytest.raises(SystemExit):
        run_cli(mod, ["headlines"], monkeypatch)


# --------------------------------------------------------------------------- #
# auth precondition
# --------------------------------------------------------------------------- #


def test_missing_key_exits(monkeypatch):
    monkeypatch.delenv("GNEWS_API_KEY", raising=False)
    # urlopen is patched so a network attempt would surface as a recorded call,
    # but get_api_key() should sys.exit before api_fetch reaches it.
    fake = patch_urlopen(monkeypatch, mod, [{"totalArticles": 0, "articles": []}])
    with pytest.raises(SystemExit):
        run_cli(mod, ["search", "AI"], monkeypatch)
    assert fake.calls == []
