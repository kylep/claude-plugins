#!/usr/bin/env python3
"""OpenObserve CLI: query logs, list streams, list/get alerts.

Ported from a Python MCP server (apps/mcp-servers/openobserve/server.py).
Requires:
  O2_URL    — base URL incl. path prefix (e.g. http://localhost:5080/obs)
  O2_TOKEN  — base64('user:pass') for Basic auth
  O2_ORG    — organization (default 'default')

Usage:
  openobserve.py search-logs "SELECT * FROM k8s_logs WHERE ..." [--start 1h] [--end now] [--limit 100]
  openobserve.py error-summary [--period 1h]
  openobserve.py recent-errors [--limit 20] [--namespace NS] [--period 1h]
  openobserve.py list-streams [--type logs|metrics|traces]
  openobserve.py stream-schema [--stream NAME]
  openobserve.py list-alerts
  openobserve.py get-alert ALERT_ID
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_STREAM = "k8s_logs"
DEFAULT_TIMEOUT = 30


def get_url() -> str:
    url = os.environ.get("O2_URL")
    if not url:
        sys.exit("O2_URL environment variable is not set")
    return url.rstrip("/")


def get_token() -> str:
    token = os.environ.get("O2_TOKEN")
    if not token:
        sys.exit("O2_TOKEN environment variable is not set (base64 of 'user:pass')")
    return token


def get_org() -> str:
    return os.environ.get("O2_ORG", "default")


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Basic {get_token()}",
        "Content-Type": "application/json",
    }


def parse_relative(s: str) -> int:
    m = re.fullmatch(r"(\d+)([mhdw])", s.strip().lower())
    if not m:
        sys.exit(
            f"Invalid relative time: {s!r}. Use e.g. '30m', '1h', '24h', '7d'."
        )
    val, unit = int(m.group(1)), m.group(2)
    return val * {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]


def to_microseconds(t: str | None, default_ago: str = "1h") -> int:
    now_us = int(time.time() * 1_000_000)
    if t is None:
        return now_us - parse_relative(default_ago) * 1_000_000
    t = t.strip()
    if re.fullmatch(r"\d+[mhdw]", t, re.IGNORECASE):
        return now_us - parse_relative(t) * 1_000_000
    if t.isdigit() and len(t) >= 13:
        return int(t) * 1_000
    try:
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1_000_000)
    except ValueError:
        sys.exit(
            f"Cannot parse time: {t!r}. Use ISO 8601, Unix ms, or relative (e.g. '1h')."
        )


def http_get(path: str, params: dict | None = None) -> Any:
    url = f"{get_url()}{path}"
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers=headers(), method="GET")
    try:
        with urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        sys.exit(
            f"OpenObserve API error {e.code}: {e.read().decode('utf-8', errors='replace')}"
        )


def http_post(path: str, body: dict) -> Any:
    url = f"{get_url()}{path}"
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers=headers(), method="POST")
    try:
        with urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        sys.exit(
            f"OpenObserve API error {e.code}: {e.read().decode('utf-8', errors='replace')}"
        )


def search(sql: str, start_us: int, end_us: int, size: int = 100) -> Any:
    body = {
        "query": {
            "sql": sql,
            "start_time": start_us,
            "end_time": end_us,
            "from": 0,
            "size": size,
        }
    }
    return http_post(f"/api/{get_org()}/_search", body)


def cmd_search_logs(args: argparse.Namespace) -> None:
    now_us = int(time.time() * 1_000_000)
    st = to_microseconds(args.start)
    et = now_us if args.end.strip().lower() == "now" else to_microseconds(args.end)
    result = search(args.sql, st, et, args.limit)
    took = result.get("took", 0)
    total = result.get("total", 0)
    hits = result.get("hits", [])
    print(f"Query took {took}ms. {total} total matches, returning {len(hits)}.")
    for h in hits:
        print(json.dumps(h, default=str))


def cmd_error_summary(args: argparse.Namespace) -> None:
    now_us = int(time.time() * 1_000_000)
    st = to_microseconds(args.period)
    sql = (
        "SELECT log_level, k8s_namespace, k8s_pod, COUNT(*) as count "
        f"FROM {DEFAULT_STREAM} "
        "WHERE log_level IN ('error', 'ERROR', 'warning', 'WARNING', 'warn', 'WARN', "
        "'critical', 'CRITICAL', 'fatal', 'FATAL') "
        "GROUP BY log_level, k8s_namespace, k8s_pod "
        "ORDER BY count DESC"
    )
    result = search(sql, st, now_us, 1000)
    hits = result.get("hits", [])
    if not hits:
        print(f"No errors or warnings in the last {args.period}.")
        return
    print(f"Error/warning summary for the last {args.period}:")
    print(f"{'Level':<10} {'Namespace':<25} {'Pod':<45} {'Count':>6}")
    print("-" * 90)
    for h in hits:
        print(
            f"{h.get('log_level', '?'):<10} "
            f"{h.get('k8s_namespace', '?'):<25} "
            f"{h.get('k8s_pod', '?'):<45} "
            f"{h.get('count', 0):>6}"
        )


def cmd_recent_errors(args: argparse.Namespace) -> None:
    now_us = int(time.time() * 1_000_000)
    st = to_microseconds(args.period)
    where = (
        "WHERE log_level IN ('error', 'ERROR', 'critical', 'CRITICAL', 'fatal', 'FATAL')"
    )
    if args.namespace:
        # OpenObserve SQL accepts string literals — single-quote escape.
        ns = args.namespace.replace("'", "''")
        where += f" AND k8s_namespace = '{ns}'"
    sql = (
        f"SELECT _timestamp, k8s_namespace, k8s_pod, k8s_container, message "
        f"FROM {DEFAULT_STREAM} {where} "
        f"ORDER BY _timestamp DESC LIMIT {args.limit}"
    )
    result = search(sql, st, now_us, args.limit)
    hits = result.get("hits", [])
    if not hits:
        print(f"No errors in the last {args.period}.")
        return
    print(f"{len(hits)} recent errors (last {args.period}):")
    for h in hits:
        msg = h.get("message", "")
        if len(msg) > 300:
            msg = msg[:300] + "..."
        print(
            f"\n[{h.get('_timestamp', '')}] "
            f"{h.get('k8s_namespace', '?')}/{h.get('k8s_pod', '?')}"
        )
        print(f"  {msg}")


def cmd_list_streams(args: argparse.Namespace) -> None:
    params = {"type": args.type} if args.type else None
    data = http_get(f"/api/{get_org()}/streams", params)
    streams = data.get("list", [])
    if not streams:
        print("No streams found.")
        return
    print(f"{'Name':<30} {'Type':<10} {'Docs':>10} {'Size (MB)':>10}")
    print("-" * 65)
    for s in streams:
        stats = s.get("stats", {})
        print(
            f"{s.get('name', '?'):<30} "
            f"{s.get('stream_type', '?'):<10} "
            f"{stats.get('doc_num', 0):>10} "
            f"{stats.get('storage_size', 0):>10.1f}"
        )


def cmd_stream_schema(args: argparse.Namespace) -> None:
    data = http_get(
        f"/api/{get_org()}/streams",
        {"type": "logs", "fetchSchema": "true"},
    )
    streams = data.get("list", [])
    target = next((s for s in streams if s.get("name") == args.stream), None)
    if not target:
        sys.exit(f"Stream '{args.stream}' not found.")
    schema = target.get("schema", [])
    if not schema:
        print(f"No schema available for '{args.stream}'.")
        return
    print(f"Schema for '{args.stream}' ({len(schema)} fields):")
    print(f"{'Field':<30} {'Type':<15}")
    print("-" * 45)
    for f in sorted(schema, key=lambda x: x.get("name", "")):
        print(f"{f.get('name', '?'):<30} {f.get('type', '?'):<15}")


def cmd_list_alerts(_args: argparse.Namespace) -> None:
    data = http_get(f"/api/v2/{get_org()}/alerts")
    alerts = data.get("list", [])
    if not alerts:
        print("No alerts configured.")
        return
    print(f"{len(alerts)} alerts:")
    for a in alerts:
        status = "enabled" if a.get("enabled") else "disabled"
        print(f"  [{a.get('id', '?')}] {a.get('name', '?')} ({status})")


def cmd_get_alert(args: argparse.Namespace) -> None:
    data = http_get(f"/api/v2/{get_org()}/alerts/{args.alert_id}")
    print(json.dumps(data, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="openobserve.py", description="Query OpenObserve."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search-logs", help="Run a SQL query against logs.")
    p.add_argument("sql")
    p.add_argument("--start", default="1h")
    p.add_argument("--end", default="now")
    p.add_argument("--limit", type=int, default=100)

    p = sub.add_parser(
        "error-summary", help="Error/warning summary grouped by namespace and pod."
    )
    p.add_argument("--period", default="1h")

    p = sub.add_parser("recent-errors", help="Recent error log lines.")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--namespace", default="")
    p.add_argument("--period", default="1h")

    p = sub.add_parser("list-streams", help="List streams.")
    p.add_argument("--type", choices=["logs", "metrics", "traces"], default="")

    p = sub.add_parser("stream-schema", help="Get a stream's field schema.")
    p.add_argument("--stream", default=DEFAULT_STREAM)

    sub.add_parser("list-alerts", help="List configured alerts.")

    p = sub.add_parser("get-alert", help="Get details of one alert.")
    p.add_argument("alert_id")

    args = parser.parse_args()
    dispatch = {
        "search-logs": cmd_search_logs,
        "error-summary": cmd_error_summary,
        "recent-errors": cmd_recent_errors,
        "list-streams": cmd_list_streams,
        "stream-schema": cmd_stream_schema,
        "list-alerts": cmd_list_alerts,
        "get-alert": cmd_get_alert,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
