---
name: writing-prds
description: Use when the user has a vague product idea, feature request, or "we should build X" prompt that needs to be scoped before any code gets written. Forces clarity through a structured interview, then writes a PRD with verifiable acceptance criteria.
---

# Writing PRDs

Turn vague product ideas into well-scoped PRDs through structured interview, research, and writing. The interview is the core value — AI agents tend to assume instead of asking. This skill forces the opposite: push back, probe, and force clarity before any code gets written.

## When to use

- "We should build X" without a concrete problem statement
- A feature request with no success metric
- A user gives you a one-paragraph idea and asks for a plan
- Anything that would otherwise jump straight to implementation

## When NOT to use

- The idea already has a written PRD or design doc — pick it up where it is
- The task is mechanical (rename, refactor, fix a known bug) — no scoping needed
- A 5-minute change — overhead exceeds value

## System context to read first

Before starting the interview, read whichever of these exist in the project so you don't propose duplicate work:

- The repo root `CLAUDE.md` / `AGENTS.md`
- The project's wiki / docs index, if any (look for `wiki/`, `docs/`, `notes/`)
- Any existing PRDs directory (look for `prds/`, `specs/`, `rfcs/`)
- Any agent or skill definitions in `.claude/` or `agents/`

Note what already exists. You will reference it during the interview to avoid duplicate scope.

## Workflow — four gated phases

```
Interview → Research → Write → Validate
```

Each phase ends with a state-change line that signals the next phase. Do not skip phases.

### Phase 1: Interview (the core value)

Ask **one question at a time** using AskUserQuestion (or, if no human is present, a subagent — see "Auto-interview mode" below). Do not batch questions. Wait for each answer.

Cover these categories:

1. **Problem clarity** — Is the problem real? Who has it? How do you know?
2. **Solution validation** — What alternatives exist? Why build this?
3. **Success criteria** — How will we know it worked? What's the metric?
4. **Constraints** — What can't change? What's off-limits?
5. **Strategic fit** — How does this align with what's already being built?
6. **Resource requirements** — What does it need to run? Compute, storage, network, money?
7. **Security implications** — What access does it need? What's the threat model?
8. **Existing stack overlap** — Does this replace or conflict with anything in the stack?
9. **Observability** — How do we know it's working? Logs, metrics, alerts?
10. **Deployment integration** — How does it fit the existing release / GitOps model?

### Rules for the interview

- **One question at a time.** Never batch five questions into one message.
- **Push back on contradictions.** If something doesn't add up, say so.
- **Probe edge cases.** "What happens when X?"
- **Flag gaps.** "You haven't mentioned Y. Is that intentional?"
- **Don't accept vague answers.** "Can you be more specific about what 'better' means?"
- **3-5 acceptance criteria per user story, not 20.** Fight scope creep at the interview.
- **Cap at 25 questions.** If you reach 25 and still lack clarity on a category, move forward and put the gap in the Open Questions section of the PRD.

### Gate

When you have enough to write the PRD, say explicitly:

> "I have enough to write a PRD. Proceeding to research."

### Phase 2: Research

Verify any factual claims that came up in the interview that you can't take at face value — third-party tools, pricing, version numbers, integration constraints. Use WebSearch and WebFetch to validate. Do not browse open-ended.

Also read the codebase for components that could be reused, and prior PRDs to understand patterns and avoid duplication.

For larger research scope, delegate to a research subagent with a specific brief — don't ask it to "look into X."

### Phase 3: Write

Write the PRD to wherever the project keeps PRDs (look for `prds/`, `specs/`, `rfcs/`, `wiki/prds/`). If no convention exists, ask once where to put it, then proceed.

#### Rules for writing

- **Every acceptance criterion must be verifiable** by an agent or human in finite time. "Should feel snappy" is not verifiable. "p95 latency under 200ms on production load" is.
- Use checklist format (`- [ ]`) for acceptance criteria so they double as a test plan.
- **No implementation details.** That's the design doc's job. If you catch yourself writing "use library X" or "deploy to Y," move it to Open Questions or delete it.
- **Non-goals are mandatory.** Draw the boundary. A PRD without non-goals is a scope-creep magnet.
- **Open Questions** section must be honest about unknowns. Don't pretend you closed gaps you didn't.
- Set `status: draft` in frontmatter.

### Phase 4: Validate

After writing, delegate to a fresh subagent with no interview context:

> Read the PRD at `<path>`. Check: (1) every acceptance criterion is testable, (2) non-goals actually exclude something, (3) no implementation details leaked in, (4) the problem section makes sense without interview context. Return a list of issues or "PASS".

If the validator returns issues, fix them. Then mark the PRD ready for review.

## Auto-interview mode

When the initial prompt includes `[AUTO-INTERVIEW]` (no human available — running in a cron or pipeline), replace AskUserQuestion with a grounded-retrieval subagent for each question. See the companion skill `grounded-retrieval-answering` for how that subagent should respond.

Use confidence tiers:
- `[EVIDENCED]` and `[INFERRED]` answers → use as solid PRD content
- `[REASONED]` answers → use with a `[reasoned]` marker in the PRD body
- `[BEST GUESS]` answers → put in Open Questions; probe harder by rephrasing the question once

The interview always completes. No abort. Confidence tiers make quality transparent without stopping the pipeline.

## Rules (non-negotiable)

- **Never skip the interview.** Even if the user says "just write it," push back. Ask at least the problem clarity and success criteria questions.
- **One question at a time.** Not a list of five.
- **No implementation details in the PRD.** Architecture lives in the design doc.
- **Push back on vague ideas.** Your job is to force clarity, not be agreeable.

## Output

A PRD that the user can review, approve, and hand off to the `writing-design-docs` skill.
