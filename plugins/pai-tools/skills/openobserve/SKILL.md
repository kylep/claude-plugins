---
name: openobserve
description: Use when querying an OpenObserve deployment for logs (SQL), recent errors or error summaries by namespace/pod, listing streams or their schemas, or listing/getting configured alerts. Requires O2_URL and O2_TOKEN (base64 of user:pass) in the environment.
---

# OpenObserve

Query an [OpenObserve](https://openobserve.ai/) instance over its HTTP API. Stdlib-only Python CLI.

## When to use

- Investigating an incident — "what errored in the last hour?"
- Pulling structured log data into a report via SQL
- Spot-checking stream schemas, doc counts, storage size
- Reviewing configured alerts

## When NOT to use

- You don't run OpenObserve. This is a niche-product skill — if you use Loki / CloudWatch / Datadog instead, this skill won't help.
- You need streaming (`tail -f`). This is request/response, not subscription.
- The query needs an aggregation OpenObserve SQL doesn't support — drop to the OpenObserve UI.

## Setup (one time)

```bash
export O2_URL="https://obs.example.com/obs"         # include path prefix if any
export O2_TOKEN="$(printf '%s:%s' user pass | base64)"
export O2_ORG="default"                              # optional, defaults to 'default'
```

## Invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/openobserve/scripts/openobserve.py" error-summary --period 6h
python3 "${CLAUDE_PLUGIN_ROOT}/skills/openobserve/scripts/openobserve.py" recent-errors --namespace pai --limit 10
python3 "${CLAUDE_PLUGIN_ROOT}/skills/openobserve/scripts/openobserve.py" \
  search-logs "SELECT k8s_pod, message FROM k8s_logs WHERE k8s_namespace = 'pai' ORDER BY _timestamp DESC" \
  --start 1h --limit 50
```

## Subcommands

- `search-logs SQL [--start 1h] [--end now] [--limit 100]`
- `error-summary [--period 1h]`
- `recent-errors [--limit 20] [--namespace NS] [--period 1h]`
- `list-streams [--type logs|metrics|traces]`
- `stream-schema [--stream NAME]` (default stream `k8s_logs`)
- `list-alerts`, `get-alert ALERT_ID`

Times accept ISO 8601 (`2026-05-20T00:00:00Z`), Unix milliseconds, or relative (`30m`, `1h`, `24h`, `7d`).

## Rules

- **`recent-errors --namespace` parameter is interpolated into SQL**, with `''` quote-escaping. Don't pass user-controlled namespaces without trusting them; for arbitrary user input, use `search-logs` with your own parameterization or a where-clause you fully control.
- **The basic-auth token is sensitive.** Don't echo `O2_TOKEN`; the script doesn't.
- **`stream-schema` requires the stream to be a logs stream.** The script queries logs streams specifically — for metrics/traces schemas use the OpenObserve UI.
- **No write tools.** This skill is read-only by design. To create or modify alerts, use the OpenObserve UI.
