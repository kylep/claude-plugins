---
name: ga4-analytics
description: Use when querying Google Analytics 4 — historical reports (sessions, users, page views, traffic sources, conversions over a date range) or realtime data (active users right now, by country/device). Requires a GA4 property and a Google service account with Viewer access.
---

# GA4 Analytics

Run reports against [Google Analytics 4](https://analytics.google.com) via the Data API v1beta. Service-account auth.

## When to use

- "How many sessions did my site get last week, by country?"
- "Which top-of-funnel pages drove the most conversions in May?"
- "How many users are on the site right now?" (realtime)
- A weekly traffic summary for a blog post or stakeholder update.

## When NOT to use

- You need GA4 *Admin* operations (manage properties, accounts, custom dimensions) — those are a different API. This skill is data-only.
- You need cohort or funnel analysis with comparisons across many segments. The simple `run-report` covers the common 80%; for serious analysis, use GA4's web UI or BigQuery export.
- You don't have GA4 set up — this won't bootstrap a property for you.

## Setup (one time)

1. Install the dependency:

   ```bash
   pip install google-analytics-data
   ```

2. Create a Google Cloud service account, download its JSON key, and grant the service account email **Viewer** access on your GA4 property (Property settings → Property access management → Add user).

3. Export env vars:

   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/ga4/service-account.json"
   export GA4_PROPERTY_ID="123456789"   # numeric property ID (Admin → Property Settings)
   ```

## Invoke

```bash
# Historical: sessions and users by country, last 28 days
python3 "${CLAUDE_PLUGIN_ROOT}/skills/ga4-analytics/scripts/ga4.py" \
  run-report --metrics activeUsers,sessions --dimensions country --limit 10

# Top pages this month
python3 "${CLAUDE_PLUGIN_ROOT}/skills/ga4-analytics/scripts/ga4.py" \
  run-report --metrics screenPageViews \
  --dimensions pagePath --start 30daysAgo --end today --limit 20

# Realtime
python3 "${CLAUDE_PLUGIN_ROOT}/skills/ga4-analytics/scripts/ga4.py" \
  realtime --metrics activeUsers --dimensions country
```

## Subcommands

- `run-report --metrics M1,M2 [--dimensions D1,D2] [--start 28daysAgo] [--end yesterday] [--limit 25] [--property ID]`
- `realtime --metrics M1[,M2] [--dimensions D1] [--limit 25] [--property ID]`

Common metric names: `activeUsers`, `sessions`, `screenPageViews`, `engagementRate`, `averageSessionDuration`, `conversions`. Common dimensions: `date`, `country`, `pagePath`, `deviceCategory`, `sessionDefaultChannelGroup`. Full lists are at <https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema>.

Dates: `YYYY-MM-DD`, `today`, `yesterday`, or relative `NdaysAgo` (e.g. `7daysAgo`, `30daysAgo`).

## Rules

- **GA4 data is confidential** (visitor counts, traffic sources, conversion rates from your private property). Don't paste raw output into public content without redacting specific numbers. Pair with `auditing-for-confidential-data`.
- **`GOOGLE_APPLICATION_CREDENTIALS` is a service account key.** Anyone with that file has the SA's permissions. Store it under `~/.config/` with `chmod 600`, never commit it. This repo's `.gitignore` blocks `*.json` named patterns commonly used for service accounts; verify before adding any `.json` near the skill.
- **The service account needs Viewer access on the GA4 property.** If you get a `PERMISSION_DENIED` error, the SA's email isn't in the property's access management page yet.
- **Realtime is the last 30 minutes only.** Don't use it for historical questions.
