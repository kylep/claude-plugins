#!/usr/bin/env python3
"""Google Search Console CLI.

Ported from a Python MCP server (apps/mcp-servers/google-search-console/server.py).
Wraps the GSC API for search analytics, URL inspection, and sitemap management.

Requires pip dependencies (the official Google libraries):
  pip install google-auth google-auth-oauthlib google-api-python-client

Env vars:
  GSC_SITE_URL          — default property URL (e.g. https://kyle.pericak.com/)
  GSC_CLIENT_SECRETS    — path to OAuth client_secrets.json (default: ./client_secrets.json)
  GSC_TOKEN_PATH        — path to the cached OAuth refresh token JSON
                          (default: ./token.json)

First run prompts an interactive OAuth flow in a browser; afterwards the
token refreshes automatically. The token file MUST NOT be committed to git.

Usage:
  gsc.py search-analytics [--start YYYY-MM-DD] [--end YYYY-MM-DD]
                          [--dimensions query,page] [--limit 25]
                          [--page-filter SUBSTR] [--query-filter SUBSTR]
                          [--site SITE_URL]
  gsc.py inspect-url URL [--site SITE_URL]
  gsc.py list-sitemaps [--site SITE_URL]
  gsc.py submit-sitemap SITEMAP_URL [--site SITE_URL]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/webmasters"]
SCRIPT_DIR = Path(__file__).parent
CLIENT_SECRETS = Path(
    os.environ.get("GSC_CLIENT_SECRETS", SCRIPT_DIR / "client_secrets.json")
)
TOKEN_PATH = Path(os.environ.get("GSC_TOKEN_PATH", SCRIPT_DIR / "token.json"))
SITE_URL_ENV = os.environ.get("GSC_SITE_URL", "")
ALLOWED_DIMS = {"query", "page", "date", "device", "country"}


def write_token(creds) -> None:
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def get_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit(
            "Missing dependencies. Install with:\n"
            "  pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds or not creds.valid:
            if not CLIENT_SECRETS.exists():
                sys.exit(
                    f"OAuth client secrets not found at {CLIENT_SECRETS}. "
                    "Download from Google Cloud Console > APIs & Services > "
                    "Credentials > OAuth client ID > Download JSON. Set "
                    "GSC_CLIENT_SECRETS to point at the downloaded file."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS), SCOPES
            )
            creds = flow.run_local_server(port=0)
        write_token(creds)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def resolve_site_url(site_url: str) -> str:
    url = (site_url or SITE_URL_ENV).strip()
    if not url:
        sys.exit("No site URL — pass --site or set GSC_SITE_URL.")
    return url


def cmd_search_analytics(args: argparse.Namespace) -> None:
    url = resolve_site_url(args.site)
    service = get_service()

    today = datetime.now(timezone.utc).date()
    sd = args.start or (today - timedelta(days=28)).isoformat()
    ed = args.end or (today - timedelta(days=3)).isoformat()
    dims = [d.strip() for d in args.dimensions.split(",") if d.strip()] or ["query"]
    invalid = [d for d in dims if d not in ALLOWED_DIMS]
    if invalid:
        sys.exit(
            f"Invalid dimensions: {', '.join(invalid)}. "
            f"Allowed: {', '.join(sorted(ALLOWED_DIMS))}"
        )
    limit = max(1, min(args.limit, 25000))

    body: dict = {
        "startDate": sd,
        "endDate": ed,
        "dimensions": dims,
        "rowLimit": limit,
        "dataState": "all",
    }
    filters = []
    if args.page_filter:
        filters.append(
            {"dimension": "page", "operator": "contains", "expression": args.page_filter}
        )
    if args.query_filter:
        filters.append(
            {"dimension": "query", "operator": "contains", "expression": args.query_filter}
        )
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]

    result = service.searchanalytics().query(siteUrl=url, body=body).execute()
    rows = result.get("rows", [])
    if not rows:
        print(f"No search analytics data for {sd} to {ed}.")
        return

    print(f"Search analytics for {url} ({sd} to {ed}), {len(rows)} rows:")
    print()
    headers = [d.capitalize() for d in dims]
    print(
        f"{'  '.join(f'{h:<30}' for h in headers)}  "
        f"{'Clicks':>8}  {'Impr':>8}  {'CTR':>7}  {'Pos':>6}"
    )
    print("-" * (30 * len(dims) + 40))
    for row in rows:
        keys = row.get("keys", [])
        key_str = "  ".join(f"{k:<30}" for k in keys)
        print(
            f"{key_str}  "
            f"{row.get('clicks', 0):>8}  "
            f"{row.get('impressions', 0):>8}  "
            f"{row.get('ctr', 0):>6.1%}  "
            f"{row.get('position', 0):>6.1f}"
        )


def cmd_inspect_url(args: argparse.Namespace) -> None:
    url = resolve_site_url(args.site)
    service = get_service()
    result = (
        service.urlInspection()
        .index()
        .inspect(body={"inspectionUrl": args.page_url, "siteUrl": url})
        .execute()
    )
    inspection = result.get("inspectionResult", {})
    idx = inspection.get("indexStatusResult", {})
    rich = inspection.get("richResultsResult", {})

    print(f"URL Inspection: {args.page_url}")
    print()
    print("## Indexing")
    print(f"  Verdict:        {idx.get('verdict', 'UNKNOWN')}")
    print(f"  Coverage:       {idx.get('coverageState', 'N/A')}")
    print(f"  Indexing state: {idx.get('indexingState', 'N/A')}")
    print(f"  Page fetch:     {idx.get('pageFetchState', 'N/A')}")
    print(f"  Robots.txt:     {idx.get('robotsTxtState', 'N/A')}")
    print(f"  Last crawl:     {idx.get('lastCrawlTime', 'N/A')}")
    print(f"  Crawled as:     {idx.get('crawledAs', 'N/A')}")
    print(f"  Google canon:   {idx.get('googleCanonical', 'N/A')}")
    print(f"  User canon:     {idx.get('userCanonical', 'N/A')}")
    referring = idx.get("referringUrls", [])
    if referring:
        print(f"  Referring URLs: {', '.join(referring[:5])}")
    if rich:
        print()
        print("## Rich Results")
        print(f"  Verdict: {rich.get('verdict', 'UNKNOWN')}")
        for item in rich.get("detectedItems", []):
            print(f"  - {item.get('richResultType', '?')}")
            for issue in item.get("items", []):
                for i in issue.get("issues", []):
                    print(
                        f"    Issue: {i.get('issueMessage', '?')} "
                        f"({i.get('severity', '?')})"
                    )


def cmd_list_sitemaps(args: argparse.Namespace) -> None:
    url = resolve_site_url(args.site)
    service = get_service()
    result = service.sitemaps().list(siteUrl=url).execute()
    sitemaps = result.get("sitemap", [])
    if not sitemaps:
        print(f"No sitemaps found for {url}.")
        return
    print(f"Sitemaps for {url}:")
    print()
    print(
        f"{'Path':<60}  {'Type':<12}  {'Submitted':<12}  "
        f"{'Errors':>6}  {'Warnings':>8}"
    )
    print("-" * 105)
    for sm in sitemaps:
        submitted_raw = sm.get("lastSubmitted") or ""
        submitted = submitted_raw[:10] if submitted_raw else "?"
        print(
            f"{sm.get('path', '?'):<60}  "
            f"{sm.get('type', '?'):<12}  "
            f"{submitted:<12}  "
            f"{sm.get('errors', 0):>6}  "
            f"{sm.get('warnings', 0):>8}"
        )
        for content in sm.get("contents", []):
            print(
                f"  └─ {content.get('type', '?')}: "
                f"{content.get('submitted', '?')} submitted, "
                f"{content.get('indexed', '?')} indexed"
            )


def cmd_submit_sitemap(args: argparse.Namespace) -> None:
    url = resolve_site_url(args.site)
    service = get_service()
    service.sitemaps().submit(siteUrl=url, feedpath=args.sitemap_url).execute()
    print(f"Sitemap submitted: {args.sitemap_url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gsc.py", description="Google Search Console CLI."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search-analytics", help="Search performance data.")
    p.add_argument("--start", help="YYYY-MM-DD (default: 28 days ago).")
    p.add_argument("--end", help="YYYY-MM-DD (default: 3 days ago).")
    p.add_argument(
        "--dimensions",
        default="query",
        help="Comma-separated: query,page,date,device,country (default 'query').",
    )
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--page-filter", default="")
    p.add_argument("--query-filter", default="")
    p.add_argument("--site", default="")

    p = sub.add_parser("inspect-url", help="Inspect a single URL's index status.")
    p.add_argument("page_url")
    p.add_argument("--site", default="")

    p = sub.add_parser("list-sitemaps", help="List registered sitemaps.")
    p.add_argument("--site", default="")

    p = sub.add_parser("submit-sitemap", help="Submit/resubmit a sitemap.")
    p.add_argument("sitemap_url")
    p.add_argument("--site", default="")

    args = parser.parse_args()
    dispatch = {
        "search-analytics": cmd_search_analytics,
        "inspect-url": cmd_inspect_url,
        "list-sitemaps": cmd_list_sitemaps,
        "submit-sitemap": cmd_submit_sitemap,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
