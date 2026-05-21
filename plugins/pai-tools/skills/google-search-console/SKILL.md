---
name: google-search-console
description: Use when querying Google Search Console for search analytics (queries, clicks, impressions, CTR, position), inspecting a single URL's index status, or listing/submitting sitemaps. Requires Google OAuth setup (client_secrets.json + cached token.json). Wraps the official Search Console API v1.
---

# Google Search Console

Query GSC for search performance, URL inspection, and sitemap management. Wraps the official `searchconsole/v1` API.

## When to use

- "What queries drove traffic to my site last 28 days?"
- "Why isn't `/some-post.html` ranking — what does GSC see?"
- "Is my sitemap submitted? How many URLs indexed?"
- A weekly SEO review that needs query + page performance pulls

## When NOT to use

- You don't own the GSC property — you can only query properties your Google account is verified on.
- You need real-time data — GSC has a 2-3 day data delay; default `end_date` is 3 days ago for that reason.
- You want to manually request re-indexing of a URL — that's only available in the GSC web UI. (The API does support `submit-sitemap`, which is a write, but no per-URL re-index request.)

## Setup (one time, but more involved than the other tools)

This skill needs **Google OAuth**. The first call opens a browser to authorize. Afterwards the cached refresh token does the work.

1. Install the Google Python libraries:

   ```bash
   pip install google-auth google-auth-oauthlib google-api-python-client
   ```

2. In Google Cloud Console, create an OAuth client (type: **Desktop**) for your project, then download the JSON:

   - APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop app → Download JSON.

3. Save the file somewhere outside this skill's directory (do **not** commit it). Point the script at it via env var:

   ```bash
   export GSC_CLIENT_SECRETS="$HOME/.config/gsc/client_secrets.json"
   export GSC_TOKEN_PATH="$HOME/.config/gsc/token.json"   # will be written on first run
   export GSC_SITE_URL="https://your-site.com/"
   ```

4. First invocation triggers the browser OAuth flow once; subsequent runs use the cached refresh token.

## Invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/google-search-console/scripts/gsc.py" \
  search-analytics --dimensions query,page --limit 50

python3 "${CLAUDE_PLUGIN_ROOT}/skills/google-search-console/scripts/gsc.py" \
  inspect-url https://your-site.com/some-post.html

python3 "${CLAUDE_PLUGIN_ROOT}/skills/google-search-console/scripts/gsc.py" list-sitemaps
```

## Subcommands

- `search-analytics [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--dimensions query,page,date,device,country] [--limit 25] [--page-filter SUBSTR] [--query-filter SUBSTR] [--site URL]`
- `inspect-url URL [--site URL]`
- `list-sitemaps [--site URL]`
- `submit-sitemap SITEMAP_URL [--site URL]`

`--site` defaults to `GSC_SITE_URL`. Date defaults are 28-days-ago to 3-days-ago.

## Rules

- **NEVER commit `client_secrets.json` or `token.json`.** This repo's `.gitignore` blocks both by name. The script will refuse to start if the secrets are missing and tell you where to put them.
- **Treat GSC data as confidential.** Click counts, impressions, and query lists are private analytics. Don't paste raw GSC output into public content. Pair with the `auditing-for-confidential-data` skill before publishing anything based on this output.
- **OAuth flow is interactive.** First run opens a browser. If you're running in a headless / CI environment, generate the `token.json` interactively first on a workstation, then copy it to the headless box with `chmod 600`.
- **`submit-sitemap` is a write operation** — it tells Google to crawl. Confirm the URL before submitting.
