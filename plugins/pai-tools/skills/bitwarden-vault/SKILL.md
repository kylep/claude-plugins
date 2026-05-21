---
name: bitwarden-vault
description: Use when the user wants to read, create, edit, delete, or generate items in their Bitwarden vault from a Claude Code session — looking up a credential, rotating a password, adding a new login, listing items by folder. Wraps the official `bw` CLI. Requires the Bitwarden CLI installed and BW_SESSION exported from `bw unlock`.
---

# Bitwarden Vault

Wraps the official Bitwarden CLI (`bw`) so Claude can read and write the vault from a session.

## When to use

- "What's the password for X?"
- "Generate a new password and save it to a Bitwarden item."
- "Show me all my AWS-related logins."
- "Rotate this credential — update the entry in Bitwarden."
- "Sync my vault."

## When NOT to use

- The user is asking about secrets that should NOT be in Bitwarden (production database keys handled by a secrets manager, deploy tokens in Vault, etc.). Route them to the right tool.
- The user wants to share a secret with someone — use Bitwarden Send through the web UI, not the CLI.
- You don't have a `BW_SESSION` and the user isn't around to run `bw unlock` — stop and ask.

## Setup (one time)

1. Install the Bitwarden CLI: <https://bitwarden.com/help/cli/>
2. `bw login` (interactive)
3. `bw unlock` → exports `BW_SESSION="..."`. Put the export in the shell that runs Claude Code (the session expires after a configurable timeout).

## Invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/bitwarden-vault/scripts/bitwarden.py" status
python3 "${CLAUDE_PLUGIN_ROOT}/skills/bitwarden-vault/scripts/bitwarden.py" list-items --search aws
python3 "${CLAUDE_PLUGIN_ROOT}/skills/bitwarden-vault/scripts/bitwarden.py" get-item "AWS Production Console"
python3 "${CLAUDE_PLUGIN_ROOT}/skills/bitwarden-vault/scripts/bitwarden.py" generate-password --length 32
```

### Subcommands

| Subcommand | What it does |
|---|---|
| `status` | Vault status (locked/unlocked, last sync, user email). |
| `sync` | Sync the local cache with the Bitwarden server. |
| `list-items [--search TERM] [--folder-id ID] [--collection-id ID]` | List items, optionally filtered. Does not include passwords in output. |
| `get-item IDENTIFIER` | Get one item by ID or exact name. **Includes the password in output.** |
| `create-item NAME [--username U] [--password P] [--uri URL] [--notes N] [--folder-id F]` | Create a new login item. |
| `edit-item ID [--name ...] [--username ...] [--password ...] [--uri ...] [--notes ...]` | Edit fields on an existing item. Only specified fields are changed. Fails on non-login items if login fields are passed. |
| `delete-item ID` | Move an item to the trash (Bitwarden's recoverable delete). |
| `generate-password [--length N] [--no-uppercase] [--no-lowercase] [--no-numbers] [--no-special]` | Generate a secure password via `bw generate`. |
| `list-folders` | List all folders in the vault. |

## Sync caveat (important)

The local `bw` cache is **not** auto-updated. If items may have been changed on another machine:

```bash
python3 .../bitwarden.py sync
```

…before `list-items` or `get-item`. Always sync after `create-item`, `edit-item`, or `delete-item` so other tools see the change.

## Rules

- **Never echo a password to a public channel.** `get-item` prints passwords to stdout for your use in the session. Do not paste it into a PR description, a chat message, a commit message, or a public log.
- **`BW_SESSION` is a session token.** Treat it like a password. Do not log it, do not print it back, do not pass it as a CLI argument to another tool.
- **Don't store secrets in `notes` if they belong in the password field.** Notes are visible in `list-items` even without `get-item`.
- **`delete-item` is recoverable from trash** (via Bitwarden web UI). Permanent deletion goes through the web UI, not this script.
- **Sync after writes, sync before reads** if cross-machine changes are possible. The script does not sync automatically.
