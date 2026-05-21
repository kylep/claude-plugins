#!/usr/bin/env python3
"""Google Analytics 4 CLI — run reports and realtime reports.

Fresh wrapper around the GA4 Data API v1beta using Google's official SDK.

Requires pip dependency:
  pip install google-analytics-data

Auth:
  GOOGLE_APPLICATION_CREDENTIALS  — path to a service account JSON key with
                                    "Viewer" access on the GA4 property
  GA4_PROPERTY_ID                  — numeric property ID (e.g. 527184342),
                                     or pass --property on each call

Usage:
  ga4.py run-report --metrics activeUsers,sessions [--dimensions date,country]
                    [--start 28daysAgo] [--end yesterday] [--limit 25]
                    [--property ID]
  ga4.py realtime --metrics activeUsers [--dimensions country] [--limit 25]
                  [--property ID]
"""

from __future__ import annotations

import argparse
import os
import sys

def _import_sdk():
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunRealtimeReportRequest,
            RunReportRequest,
        )
    except ImportError:
        sys.exit(
            "Missing dependency. Install with:\n  pip install google-analytics-data"
        )
    return (
        BetaAnalyticsDataClient,
        DateRange,
        Dimension,
        Metric,
        RunRealtimeReportRequest,
        RunReportRequest,
    )


def get_property(arg_property: str) -> str:
    pid = (arg_property or os.environ.get("GA4_PROPERTY_ID") or "").strip()
    if not pid:
        sys.exit("Property ID — pass --property or set GA4_PROPERTY_ID.")
    return pid if pid.startswith("properties/") else f"properties/{pid}"


def get_client():
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sys.exit(
            "GOOGLE_APPLICATION_CREDENTIALS environment variable is not set. "
            "Point it at the service account JSON key with Viewer access on "
            "your GA4 property."
        )
    BetaAnalyticsDataClient, *_ = _import_sdk()
    return BetaAnalyticsDataClient()


def split_csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def print_rows(rows, dim_headers: list[str], metric_headers: list[str]) -> None:
    if not rows:
        print("No data.")
        return
    headers = dim_headers + metric_headers
    widths = [max(20, len(h)) for h in headers]
    print("  ".join(f"{h:<{w}}" for h, w in zip(headers, widths)))
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    for row in rows:
        dvals = [d.value for d in row.dimension_values]
        mvals = [m.value for m in row.metric_values]
        vals = dvals + mvals
        print("  ".join(f"{v:<{w}}" for v, w in zip(vals, widths)))


def cmd_run_report(args: argparse.Namespace) -> None:
    (
        _,
        DateRange,
        Dimension,
        Metric,
        _RT,
        RunReportRequest,
    ) = _import_sdk()
    client = get_client()
    metrics = [Metric(name=m) for m in split_csv(args.metrics)]
    dimensions = [Dimension(name=d) for d in split_csv(args.dimensions)] if args.dimensions else []
    if not metrics:
        sys.exit("--metrics is required (comma-separated, e.g. activeUsers,sessions).")

    request = RunReportRequest(
        property=get_property(args.property),
        date_ranges=[DateRange(start_date=args.start, end_date=args.end)],
        dimensions=dimensions,
        metrics=metrics,
        limit=args.limit,
    )
    resp = client.run_report(request)
    dim_h = [h.name for h in resp.dimension_headers]
    met_h = [h.name for h in resp.metric_headers]
    print(f"GA4 report ({args.start} → {args.end}), {len(resp.rows)} rows:")
    print()
    print_rows(resp.rows, dim_h, met_h)


def cmd_realtime(args: argparse.Namespace) -> None:
    (
        _,
        _DR,
        Dimension,
        Metric,
        RunRealtimeReportRequest,
        _RR,
    ) = _import_sdk()
    client = get_client()
    metrics = [Metric(name=m) for m in split_csv(args.metrics)]
    dimensions = [Dimension(name=d) for d in split_csv(args.dimensions)] if args.dimensions else []
    if not metrics:
        sys.exit("--metrics is required (comma-separated, e.g. activeUsers).")

    request = RunRealtimeReportRequest(
        property=get_property(args.property),
        dimensions=dimensions,
        metrics=metrics,
        limit=args.limit,
    )
    resp = client.run_realtime_report(request)
    dim_h = [h.name for h in resp.dimension_headers]
    met_h = [h.name for h in resp.metric_headers]
    print(f"GA4 realtime, {len(resp.rows)} rows:")
    print()
    print_rows(resp.rows, dim_h, met_h)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ga4.py", description="GA4 Data API CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run-report", help="Standard report (historical data).")
    p.add_argument("--metrics", required=True, help="Comma-separated metric names.")
    p.add_argument("--dimensions", default="", help="Comma-separated dimension names.")
    p.add_argument("--start", default="28daysAgo", help="Start (date or relative).")
    p.add_argument("--end", default="yesterday", help="End (date or relative).")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--property", default="", help="GA4 property ID.")

    p = sub.add_parser("realtime", help="Realtime report (last 30 minutes).")
    p.add_argument("--metrics", required=True)
    p.add_argument("--dimensions", default="")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--property", default="")

    args = parser.parse_args()
    {
        "run-report": cmd_run_report,
        "realtime": cmd_realtime,
    }[args.command](args)


if __name__ == "__main__":
    main()
