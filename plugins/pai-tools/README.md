# pai-tools

SDK-wrapper skills, bundled with their code. Each skill is a small Python script (stdlib only where possible) plus a `SKILL.md` that tells Claude when to use it. No `npm install`, no compile step, no MCP host required.

These are conversions of MCP servers from my private workspace — the ones that were "really just SDK wrappers" rather than infrastructure-coupled integrations.

## Install

```text
/plugin marketplace add kylep/claude-plugins
/plugin install pai-tools@pai-plugins
```

## What's in here

| Skill | Wraps | Requires |
|---|---|---|
| [`openrouter-usage`](skills/openrouter-usage/SKILL.md) | OpenRouter REST API (`/key`, `/models`) | `OPENROUTER_API_KEY` env var |
| [`google-news`](skills/google-news/SKILL.md) | gnews.io REST API | `GNEWS_API_KEY` env var |
| [`bitwarden-vault`](skills/bitwarden-vault/SKILL.md) | Bitwarden CLI (`bw`) | Bitwarden CLI installed, `BW_SESSION` exported |
| [`macos-desktop-control`](skills/macos-desktop-control/SKILL.md) | `screencapture` + `cliclick` | macOS, `brew install cliclick` |

All scripts use Python stdlib only — `urllib.request`, `json`, `subprocess`, `argparse`. No third-party deps to install.

## Layout

Each skill follows the same shape:

```
skills/<skill-name>/
├── SKILL.md              # when to use + how to invoke
└── scripts/<name>.py     # CLI: subcommands, --help, prints to stdout
```

Claude invokes each script via Bash, reading `${CLAUDE_PLUGIN_ROOT}` to locate it.

## Why scripts and not MCP servers

The original implementations were MCP servers (TypeScript with `@modelcontextprotocol/sdk`). For SDK wrappers — stateless, one-shot API calls — a small CLI script gives you the same capability with:

- Zero install footprint (no `npm install`, no build, no Node version).
- No MCP host process running between invocations.
- Trivial portability — every machine with Python 3 can run them.
- Discoverable via skill descriptions, so Claude knows when to invoke them.

The cost is the loss of native MCP type-safety and tool discovery, but at this scale that's not a meaningful loss.

## Adding a new tool

1. Create `skills/<new-tool>/scripts/<script>.py`. Use stdlib if you can; document any pip deps in the SKILL.md if you can't.
2. Write a `SKILL.md` describing the trigger conditions and invocation.
3. Smoke-test with `python3 scripts/<script>.py --help`.

## License

MIT — see the [repository LICENSE](../../LICENSE).
