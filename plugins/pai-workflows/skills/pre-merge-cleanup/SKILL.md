---
name: pre-merge-cleanup
description: Use before merging a branch, PR, or MR, once the work is complete. Re-reads the full diff as a single change and strips out what was added along the way but no longer earns its place — unused imports, unreachable functions, low-value or obsolete tests, speculative abstractions, mid-stream patterns that aren't the right final call. Distinct from bug/security code review.
---

# Pre-Merge Cleanup

During development, changes accrete: scaffolding, a helper used once, a pattern tried then
half-replaced, a test for a branch that was later deleted. Each made sense *at the time*.
Viewed as a whole at merge time, many don't. This skill re-reads the finished change as a
single diff and removes what isn't justified in the merged result. It is **not** a bug or
security review — the question is only: *does each thing in this diff earn its place?*

## When to use

- A branch / PR / MR is complete and about to be merged
- Wrapping up a feature, just before opening or merging the PR
- Asked to "clean up", "tighten", or "review the diff before merge"

## When NOT to use

- Hunting for bugs, security issues, or correctness — that is code review's job
- Mid-development, when changes are still in flux
- Refactoring code the branch didn't touch

## Scope (read first — these bound everything below)

- **Only act on what this branch introduced.** Compute the net diff against the merge
  target (`git diff <base>...HEAD`). Pre-existing code is out of scope — never touch it.
- **Behavior must not change.** The shipped feature behaves identically after cleanup. If
  a removal *could* alter runtime behavior, flag it — do not cut it.

## What earns review

- Unused imports, variables, or dead code the branch added
- Functions / helpers added but never called (unreachable)
- Leftover debug output, commented-out code, untracked TODOs
- Low-value or obsolete tests: tests for code paths this branch removed, tautological
  tests, or duplicates of existing coverage — high bar (see Rules)
- Speculative abstractions / premature generalization introduced along the way
- Mid-stream patterns that aren't the right call in the final shape (e.g. a parameter
  added for flexibility nothing uses, two ways of doing one thing)

## Process (auto-apply, then report)

1. **Get the change.** Determine the merge target and read the full net diff, file by
   file — judge the change as a whole, not hunk by hunk.
2. **Judge each accreted item** against "does this earn its place in the merged result?"
3. **Apply the high-confidence, behavior-preserving removals.** When unsure, leave it and
   record it under Flagged instead of cutting.
4. **Verify.** Run the project's tests / build / linters after pruning. If any removal
   breaks them, revert that specific removal. Never leave the branch broken.
5. **Report** what was removed and what was flagged-but-left.

## Rules (non-negotiable)

1. **Branch-only.** Prune only what this branch introduced; pre-existing code is untouchable.
2. **No behavior change.** If a cut could alter what ships, flag it — don't apply it.
3. **Verify before done.** Tests/build/lint must pass after cleanup; revert any cut that breaks them.
4. **High confidence to cut, otherwise flag.** Destructive edits need a clear, stated reason.
5. **Tests need a real reason.** Remove a test only if it covers deleted code, is
   tautological, or duplicates existing coverage. Never remove a test that exercises
   behavior this branch ships.
6. **Stay in lane.** Don't fix bugs or restyle code here — only remove what doesn't earn its place.

## Report format

```
## Pre-merge cleanup

### Removed
- `path` — <what> — <why it didn't earn its place>

### Flagged (left in — your call)
- `path` — <what> — <why it's uncertain>

### Verification
- <tests / build / lint result after cleanup>
```
