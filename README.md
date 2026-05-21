# pai-plugins

Pericak AI — public marketplace of Claude Code plugins by [Kyle Pericak](https://kyle.pericak.com).

## Install

```text
/plugin marketplace add kylep/claude-plugins
/plugin install pai-workflows@pai-plugins
/plugin install pai-tools@pai-plugins
```

Refresh after I push: `/plugin marketplace update pai-plugins`.

## pai-workflows

- **writing-prds**: interview-driven PRD generation from a vague idea
- **writing-design-docs**: PRD → architecture doc with dependency-ordered task breakdown
- **grounded-retrieval-answering**: confidence-tiered answers from repo evidence (auto-interview companion)
- **gathering-sourced-facts**: structured research brief with sources and confidence levels
- **synthesizing-research**: compare/contrast multiple research reports into shared/unique/contradiction
- **ingesting-external-research**: validate claims, ADOPT/ADAPT/SKIP triage with self-review
- **auditing-for-confidential-data**: pre-publish content audit (auth'd-data leaks, OWASP LLM 01/05/06)

## pai-tools

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
.claude-plugin/marketplace.json
plugins/
├── pai-workflows/
│   ├── .claude-plugin/plugin.json
│   ├── README.md
│   └── skills/<name>/SKILL.md
└── pai-tools/
    ├── .claude-plugin/plugin.json
    ├── README.md
    └── skills/<name>/
        ├── SKILL.md
        └── scripts/<name>.py
```

New plugins drop into `plugins/<name>/` with their own `.claude-plugin/plugin.json` and `skills/` directory, then get an entry in `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`.

## License

MIT — see [LICENSE](LICENSE).
