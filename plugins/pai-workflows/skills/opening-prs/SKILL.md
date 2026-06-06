---
name: opening-prs
description: Use when opening a pull request or writing/updating a PR description — running `gh pr create`, filling in a PR body or template, or revising an existing PR's text.
---

# Opening PRs

A PR description explains the change above the code level: what it is, and above all
*why*. A reviewer should grasp the intent and impact before reading a single line of the
diff. Use this exact structure.

## When to use

- Creating a pull request (`gh pr create` or the web UI)
- Writing or revising a PR description / filling in a PR template

## When NOT to use

- Commit messages — a different concern, not governed here
- The code or comments themselves

## PR body structure

Three sections, in order, with `#` headings.

### `# Description`

Open with 1–3 sentences: what the change is about, mostly the *why*, above the code
level — the feature, fix, or capability it delivers. **Link any planning doc, design
spec, plan file, or issue** that informed the work.

Then the breakdown, one line each:

- **Problem/purpose of the change:**
- **What was changed:**
- **Why this matters:**
- **Expected impact:**

### `# Files Changed`

A table of every **non-test** file touched, with one sentence on why:

| File | Why it changed |
|------|----------------|
| `path/to/file` | … |

**Exclude test files entirely** — no rows, and no mention of them anywhere in the body.

### `# Context`

Optional. Anything else worth knowing — alternatives considered, caveats, follow-ups.
**Omit the whole section** when there is nothing real to add; never pad it.

## Rules

1. **Lead with the why.** The prose intro and "Why this matters" convey intent and
   impact, not a line-by-line account of the diff. Don't restate the prose in the
   bullets — the bullets break it down.
2. **Link the planning trail.** If a design spec, plan file, issue, or external resource
   informed the change, link it in the Description. If none exists, omit the link — never
   invent one.
3. **Files Changed is non-test only.** One row per changed non-test file, one sentence
   each. Test files never appear.
4. **Factual and tight.** Describe the change, not the work session. One sentence per
   bullet and per file row; expand only in Context, and only when it genuinely helps.
