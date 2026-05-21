---
name: writing-design-docs
description: Use when an approved PRD exists and the user wants a technical design document with architecture, alternatives, and a dependency-ordered task breakdown. Produces a plan that Claude Code's plan mode can execute directly.
---

# Writing Design Docs

Take an approved PRD and produce a technical design document that bridges product requirements to implementation. The output's Task Breakdown section is meant to feed directly into Claude Code's plan mode.

This skill is the second half of a two-skill pair with `writing-prds`. Use them together for new features; use this one alone when a PRD already exists.

## When to use

- A PRD is approved and someone needs to architect the implementation
- A design needs Alternatives Considered for each significant decision
- The work needs to be broken into discrete, dependency-ordered tasks before coding starts

## When NOT to use

- No PRD yet — go to `writing-prds` first
- The task is one coherent change in one file — design doc overhead exceeds value
- The architecture is already fully documented elsewhere

## System context to read first

- The target PRD (discovered in Phase 0)
- Repo root `CLAUDE.md` / `AGENTS.md`
- The project's design-docs directory and its template, if any
- Existing design docs (so you reuse conventions and don't duplicate)
- Components in the codebase that this design will extend or integrate with

## Workflow — five gated phases

```
Discover PRD → Interview → Research → Write → Validate
```

### Phase 0: Discover PRD

- If a PRD path is given, read it directly.
- If not, list available PRDs and ask the user which one (or, in auto-interview mode, pick the most relevant by topic and state why).
- Warn if PRD status is `draft` rather than `approved`.
- Extract and note: problem, goal, success metrics, non-goals, user stories + acceptance criteria, scope, open questions, risks.

Gate: "PRD loaded. Starting architecture interview."

### Phase 1: Interview (architecture-focused)

One question at a time. Cover:

1. **Architecture constraints** — Infrastructure, languages, frameworks, services that are off-limits or mandatory
2. **Component boundaries** — Extend existing vs. create new; where interfaces live; what owns what
3. **Data model and flow** — CRUD, storage choices, access patterns, lifecycle
4. **Integration points** — External systems, APIs, latency/reliability requirements, failure modes
5. **Operational concerns** — Deployment, monitoring, rollback strategy, non-functional requirements

Rules:
- Reference PRD acceptance criteria to ground the conversation.
- Probe edge cases: "What happens when X fails?"
- Flag gaps: "The PRD mentions Y but you haven't addressed how."
- Cap at 25 questions. Cover architecture constraints and component boundaries at minimum.

Gate: "I have enough to write the design doc. Proceeding to research."

### Phase 2: Research

Use the codebase for components that will be extended or integrated. Use prior design docs to understand conventions. Use the web only to verify external-system specifics (API contracts, library APIs, pricing tiers) — not for general browsing.

For larger external research, delegate to a research subagent with a specific brief.

### Phase 3: Write

Write the design doc to the project's design-docs directory. Use the project template if one exists.

#### Rules for writing

- Set `status: draft` and a link to the source PRD in frontmatter.
- Include at least one architecture diagram (mermaid works well for portable docs).
- **Every significant decision must have an Alternatives Considered subsection** with an Option | Pros | Cons | Verdict table. "We just picked X" is not acceptable.
- **File Change List is a first-class section.** Enumerate every file to create, modify, or delete.
- **Task Breakdown** must be dependency-ordered with stable IDs (e.g. `TASK-001`, `TASK-002`).
- Each task has: Requirement (linking back to a PRD acceptance criterion), Files, Dependencies (other TASK ids), and an acceptance checklist.
- Mark parallelizable tasks with `[P]`.
- **No implementation code.** Architecture and interfaces only. If you catch yourself writing function bodies, stop and move the detail to the task description.
- Task granularity: a single coherent change, testable in isolation. If a task touches more than 3-4 files, consider splitting it.

### Phase 4: Validate

Delegate to a fresh subagent:

> Read the design doc at `<path>` and the PRD at `<prd-path>`. Check:
> 1. Every PRD acceptance criterion is addressed by at least one task
> 2. Every task has files, acceptance criteria, and dependencies
> 3. No circular dependencies in the task graph
> 4. Alternatives Considered exists for each significant decision
> 5. Diagram is syntactically valid
> 6. No implementation code leaked in (no function bodies, only interfaces)
> 7. Document stands alone without needing interview context
> Return a list of issues or "PASS".

Fix any issues before declaring done.

## Auto-interview mode

When the initial prompt includes `[AUTO-INTERVIEW]`, replace AskUserQuestion with a grounded-retrieval subagent. See `grounded-retrieval-answering`. Use confidence tiers the same way as in `writing-prds`. If no PRD path is specified, list PRDs and pick the most relevant one based on the prompt topic — state which PRD was selected and why.

## Rules (non-negotiable)

- **Never skip the interview.** Architecture constraints and component boundaries at minimum.
- **One question at a time.**
- **Reference the PRD throughout.** Every task should trace back to a PRD acceptance criterion.
- **No implementation code.** Interfaces and contracts only.
- **Every significant decision needs Alternatives Considered.**
- **Task granularity:** single coherent change, testable in isolation.

## Output

A design doc the user can review, approve, and hand to an implementing agent as a ready-made plan.
