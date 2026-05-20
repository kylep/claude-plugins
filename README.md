# pai-plugins

**Pericak AI** — public marketplace for [Kyle Pericak](https://kyle.pericak.com)'s Claude Code plugins.

These are skills and tools extracted from my private workspace and de-personalized so other people can use them. They reflect how I think more than what your project needs — read the descriptions, install what's useful, ignore the rest.

## Install

This marketplace lives in a public GitHub repo. From any Claude Code session:

```text
/plugin marketplace add kylep/claude-plugins
/plugin install pai-workflows@pai-plugins
```

To install from a local clone instead (handy if you want to fork and tweak):

```bash
git clone https://github.com/kylep/claude-plugins ~/gh/claude-plugins
```

Then in Claude Code:

```text
/plugin marketplace add ~/gh/claude-plugins
/plugin install pai-workflows@pai-plugins
```

Refresh with `/plugin marketplace update pai-plugins` after I push changes.

## Plugins

| Plugin | What it is |
|---|---|
| [`pai-workflows`](plugins/pai-workflows) | Interview-driven PRDs and design docs, research synthesis, grounded retrieval, content security audits |

More plugins will land here over time. Each is independent — install only the ones you want.

## Repository layout

```
claude-plugins/
├── .claude-plugin/
│   └── marketplace.json            # marketplace catalog
├── plugins/
│   └── pai-workflows/               # one plugin per subdirectory
│       ├── .claude-plugin/
│       │   └── plugin.json         # plugin manifest
│       ├── README.md
│       └── skills/                 # auto-discovered
│           └── <skill-name>/SKILL.md
├── LICENSE                          # MIT
└── README.md
```

Adding a new plugin is two steps: create `plugins/<new-plugin>/` with a `.claude-plugin/plugin.json` and a `skills/` (and/or `agents/`, `commands/`) directory, then add an entry to `.claude-plugin/marketplace.json` with `"source": "./plugins/<new-plugin>"`.

## License

MIT — see [LICENSE](LICENSE).

## Contact

Issues and PRs welcome at <https://github.com/kylep/claude-plugins>. Reach me at <kyle@pericak.com> or via the contact info on [kyle.pericak.com](https://kyle.pericak.com).
