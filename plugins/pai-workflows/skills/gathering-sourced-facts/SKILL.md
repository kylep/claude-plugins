---
name: gathering-sourced-facts
description: Use when gathering facts for a blog post, doc, or claim-validation pass — anywhere a structured research brief with sources and confidence levels is needed. Forces primary-source preference and "wide before narrow" search discipline.
---

# Gathering Sourced Facts

Gather accurate, sourced facts on a topic and return a structured research brief. This skill is for building research briefs that another writer or agent will turn into prose — not for writing the prose yourself.

**Read-only.** Return findings; do not write the final document.

## When to use

- Writing a blog post that makes factual claims (versions, dates, API details, pricing)
- Validating claims in an existing draft before publication
- Building a research input for `writing-prds` or `writing-design-docs`
- A user asks "find me sources for X" or "what's the current state of Y?"

## When NOT to use

- The user wants a recommendation, not raw facts — that's analysis, not research
- The user wants you to write the final post — use this to gather, then write separately
- Quick one-line fact-check — just answer with WebFetch / WebSearch directly

## Search strategy: start wide, then narrow

A common failure mode for agents in unfamiliar territory is jumping straight to overly specific queries, which return nothing or the wrong thing. Reverse it:

1. **Broad first.** General queries to understand what exists. Skim for key terms, authors, primary sources.
2. **Map the landscape.** Identify major subtopics, competing approaches, and primary sources before going deep.
3. **Narrow progressively.** Drill into specific claims, numbers, and details only after you understand the overall picture.
4. **Cross-reference.** When multiple sources cover the same claim, note agreement or disagreement.

## Source preference

- **Primary sources beat secondary.** Official documentation, source code, API references, RFCs > blog posts > forums.
- **Recent beats old** for fast-moving topics (model names, SDK versions, API features, pricing).
- **Cite the source URL or repo path.** Not "according to the docs" — give the link.

## Per-fact confidence levels

For each fact you return:

- **verified** — primary source confirms it
- **likely** — multiple secondary sources agree, no primary source contradicts
- **uncertain** — sources conflict, or the only sources are weak

Don't speculate. If you can't verify something, list it as a gap, not a fact.

## Output format

```markdown
# Research Brief: <topic>

## <Subtopic 1>

- **Fact**: <clear statement>
  - Source: <URL or path>
  - Confidence: verified | likely | uncertain

- **Fact**: <clear statement>
  - Source: <URL or path>
  - Confidence: verified | likely | uncertain

## <Subtopic 2>
...

## Gaps

- <thing you couldn't verify or find a source for>
- <thing where sources conflict>
```

Group facts by subtopic. A brief that's just a flat list is hard to use; structure helps the writer find what they need.

## Rules

- **Prefer primary sources.** Official documentation, source code, API references.
- **If a fact has conflicting sources, note both and flag the conflict.** Don't silently pick one.
- **If you can't find a source, list it in Gaps.** Don't make things up.
- **A claim without a findable source is a gap, not a verified fact.** No matter how confident you are.
- **When in doubt, say uncertain.** Better than asserting confidence and being wrong.
- **Fast-moving topics need fresh checks.** Model versions, API features, CLI flags — always re-verify against current docs, not training data.
