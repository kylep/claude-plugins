# pai-tools

SDK-wrapper skills with bundled Python scripts. Each script is a single-file CLI invoked via Bash; most use stdlib only.

## Install

```text
/plugin marketplace add kylep/claude-plugins
/plugin install pai-tools@pai-plugins
```

## Skills

- **openrouter-usage**: OpenRouter API spend, credit balance, model pricing
- **google-news**: gnews.io search + headlines with prompt-injection sanitization
- **bitwarden-vault**: `bw` CLI wrapper — list, get, create, edit, generate
- **macos-desktop-control**: macOS `screencapture` + `cliclick`
- **discord**: Discord REST API v10 — send/read/edit/delete messages, reactions, threads, embeds
- **openobserve**: SQL log queries, error summaries, stream/alert listings
- **google-search-console**: search analytics, URL inspection, sitemap management (OAuth)
- **ga4-analytics**: Google Analytics 4 historical and realtime reports (service account)
- **linear**: Linear GraphQL — list/get/create/update issues, comments, teams, projects
- **cc-usage**: Claude Code spend and tokens from local session logs, with LiteLLM pricing

## Layout

```
skills/<skill-name>/
├── SKILL.md              # when to use + how to invoke
└── scripts/<name>.py     # CLI: subcommands, --help, prints to stdout
```

Each `SKILL.md` documents env vars, pip deps (if any), and subcommands.

## License

MIT — see the [repository LICENSE](../../LICENSE).
