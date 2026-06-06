---
name: writing-comments
description: Use when writing or editing code comments — inline (#, //) or block (/* */) — in any language, during any coding task. Also when leaving a TODO/FIXME or cleaning up existing comments.
---

# Writing Comments

A comment earns its place or it does not exist. Comments explain *why* the code is the
way it is — never what it plainly does, and never anything about how it came to be
written. This skill governs the text of inline and block code comments only; it never
changes code logic.

## When to use

- Writing or editing an inline (`#`, `//`) or block (`/* */`) comment
- Cleaning up or reviewing existing comments
- About to leave a `TODO` / `FIXME`

## When NOT to use

- Docstrings, JSDoc, or public API doc blocks — out of scope; write them normally
- Commit messages, PR descriptions, changelogs, README / prose docs
- The surrounding code — never alter logic to satisfy a comment rule

## Rules

1. **No session or process context — ever.** A comment describes the code, not the work
   that produced it. Never reference plans, WIP state, the current task, "as discussed",
   "for now", refactors you intend to do, or anything from this session. If a reader who
   never saw the conversation wouldn't need it, cut it.
2. **Brief — one line is the default.** Inline and block comments rarely exceed a single
   line. If you need a paragraph, the code likely needs restructuring (or it belongs in a
   docstring, which this skill does not govern).
3. **Prefer no comment.** Before writing one, ask: *does the code already make this
   clear?* If names and structure convey the "why", write nothing — a redundant comment is
   worse than none, because it rots. Comment only the non-obvious: a surprising
   constraint, a workaround and its reason, a deliberate edge case.
4. **TODOs are rare and always tracked.** Only leave a TODO for a real follow-up, in the
   form `TODO(TICKET-123): short description`, linked to a tracking item (Linear, Jira,
   etc.). If no ticket exists, create one with the user first — the `pai-tools:linear`
   skill can do this — then reference its ID. Never leave an untracked TODO.

## Examples

The code already says it — write nothing:
```python
count += 1  # increment count      ← delete
count += 1                          ← good
```

Explain the non-obvious "why", in one line — and keep the session out of it:
```python
time.sleep(0.2)  # Stripe rate-limits below 5 req/s                         ← good
time.sleep(0.2)  # temporary until we add the retry queue from the plan     ← bad: session bleed
```

Tracked TODO:
```python
# TODO: this is slow, fix later                              ← bad: untracked
# TODO(PER-214): replace linear scan with index lookup       ← good
```
