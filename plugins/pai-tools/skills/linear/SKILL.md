---
name: linear
description: Use when listing/getting/creating/updating Linear issues, adding comments, or listing teams and projects from a Claude Code session. Calls the Linear GraphQL API directly with a personal API key. Stdlib-only Python — no SDK to install.
---

# Linear

Drive [Linear](https://linear.app) issues through the GraphQL API. Personal API key authentication. Stdlib-only Python CLI.

## When to use

- "What's still open on PER-X project?"
- "Create a ticket for this bug, assign to me, label it Improvement."
- "Move PER-123 to In Progress and add a comment with the PR link."
- Audit who owns what across a team.

## When NOT to use

- You need attachments — this CLI doesn't support file uploads (use the Linear UI or web app).
- You need cycle/milestone management — basic CRUD only; for cycle planning, use the Linear UI.
- The action is destructive across many issues at once (bulk delete) — use the Linear UI with confirmation.

## Setup (one time)

1. Linear → Settings → API → Personal API keys → New key.
2. Export it:

   ```bash
   export LINEAR_API_KEY="lin_api_..."
   ```

   Linear's personal API keys go directly in the `Authorization` header (no `Bearer` prefix); the script handles that.

## Invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/linear/scripts/linear.py" list-issues --assignee me --state "In Progress"

python3 "${CLAUDE_PLUGIN_ROOT}/skills/linear/scripts/linear.py" get-issue PER-99

python3 "${CLAUDE_PLUGIN_ROOT}/skills/linear/scripts/linear.py" \
  create-issue --team Pericak --title "Bug: ..." --priority 2 --assignee me \
  --description "Repro: ..."

python3 "${CLAUDE_PLUGIN_ROOT}/skills/linear/scripts/linear.py" \
  update-issue PER-99 --state "Done"

python3 "${CLAUDE_PLUGIN_ROOT}/skills/linear/scripts/linear.py" \
  add-comment PER-99 "Linked PR: https://github.com/.../pull/42"
```

## Subcommands

- `list-issues [--assignee me|EMAIL|NAME] [--team] [--project] [--state] [--query] [--limit 25]`
- `get-issue PER-123` — single issue with description
- `create-issue --team NAME --title "..." [--description] [--assignee] [--state] [--priority 0-4] [--project] [--labels A,B]`
- `update-issue PER-123 [--title] [--description] [--assignee] [--state] [--priority]`
- `add-comment PER-123 "body"`
- `list-comments PER-123`
- `list-teams`, `list-projects [--team NAME]`

Priority values: `0` None, `1` Urgent, `2` High, `3` Medium, `4` Low.

## Rules

- **`LINEAR_API_KEY` is full-access to your Linear workspace.** Don't echo it; the script doesn't.
- **Mutations are immediate** — `create-issue`, `update-issue`, `add-comment` write to Linear with no confirmation step. Verify identifiers, especially when changing state on issues other people own.
- **Comment bodies are visible to everyone with access to the issue.** Treat them as public to your workspace. Don't paste secrets or credentials.
- **Label / state / assignee / project lookups are exact-match** (case-sensitive). If a create fails with "not found," check casing first.
- **Pair with `auditing-for-confidential-data`** before pasting Linear output (counts, velocities) into anything public — that's authenticated data.
