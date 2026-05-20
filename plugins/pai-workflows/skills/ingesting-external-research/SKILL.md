---
name: ingesting-external-research
description: Use when an external research document (Deep Research report, paper, style guide, third-party post) lands in the repo and the user wants to validate its claims, compare findings against the current system, and propose specific improvements with defensible reasoning.
---

# Ingesting External Research

Validate the claims in an external research document, compare findings against the current system, and propose specific improvements with reasoning the user can defend if challenged.

This is a read-only skill. You return an analysis report with ready-to-apply proposed changes; you do not modify the system files.

## When to use

- A Deep Research output lands and needs to be processed (not just read)
- A third-party style guide or best-practices doc could inform the project's conventions
- A research paper makes claims that could update how the project works
- An audit produced a long list of findings that need ADOPT / ADAPT / SKIP triage

## When NOT to use

- A simple "is this right?" fact-check — just answer the question
- The doc is a tutorial or example, not a source of recommendations
- The user already decided to apply or reject it — they want execution, not analysis

## System context to read first

Before reading the research document, read the parts of the system the research could change so you can compare against notes (not re-reads):

- Style guides, conventions docs (often in `.ruler/`, `docs/style/`, `CONTRIBUTING.md`)
- Agent / skill / command definitions (`.claude/agents/`, `.claude/skills/`, `agents/`, `skills/`)
- Repo root `CLAUDE.md` / `AGENTS.md`

Take notes on what each file covers. You'll compare research findings against these notes, not against re-reads.

## Workflow

### 1. Read system state

Read the system files above. For each section and rule, note what it covers. Build a coverage map.

### 2. Read research document(s)

Read the input document(s) sequentially, not all at once. Extract every distinct claim, finding, recommendation, or technique into a working list. If there are multiple documents, note which document each item comes from.

### 3. Assess every item (no pre-filtering)

For each item:

#### Validate the claim

Use WebSearch and WebFetch to check primary sources. Assign a status:

- **VERIFIED** — confirmed by a primary source
- **PARTIALLY VERIFIED** — partially supported or context-dependent
- **UNVERIFIED** — can't find confirming evidence
- **CONTRADICTED** — primary sources disagree

If multiple input documents exist, cross-reference: do they agree on this item?

#### Check current coverage

Compare against your notes on the system files:

- **COVERED** — the exact point is already in the system; cite the file and section
- **PARTIAL** — related coverage exists but misses this specific aspect
- **GAP** — not covered at all

#### Recommend an action

- **ADOPT** — add to the system as-is or nearly as-is
- **ADAPT** — useful but needs reshaping for this system's context
- **SKIP** — don't add

Every recommendation needs specific reasoning:
- **SKIP** must name the specific reason (already covered at `file:section`, wrong audience, not actionable, etc.)
- **ADOPT/ADAPT** must include the exact proposed text and where it goes (file, section, placement relative to existing content)

### 4. Cross-reference multiple documents

If there are multiple inputs, after the item-by-item analysis add:
- Where do the documents agree? (higher confidence)
- Where do they disagree? (flag for investigation)
- What does one cover that the other misses?
- Which document is stronger on which topics?

### 5. Self-review (the filter)

Re-examine every recommendation:

**For each SKIP:**
- "If the user challenged this, could I defend it with a specific reason?" If not, change to ADOPT or ADAPT.
- "Am I saying 'already covered' because it genuinely is, or because the topic is similar?" Verify the existing coverage actually addresses this specific point.

**For each ADOPT:**
- "Does this make the system better, or just longer?"
- "Is this duplicating something already present in different words?"

**Bias detection:**
- Skipping most items → you may be defensive about the current system.
- Adopting most items → you may be uncritical of the research.
- Flag the pattern explicitly. Note whether re-examination changed anything.

**Transparency:** record every adjustment made during self-review (original recommendation → new recommendation, with reason). If nothing changed, say so and explain why you're confident the original pass was correct.

## Output format

```markdown
# Analysis Report: <document title(s)>

## Source Assessment
<For each document: what it is, who produced it, quality.>
<If multiple: where they agree, diverge, relative strengths.>

## Item-by-Item Analysis

### <item name>
- **Claim**: <what the research says>
- **Validation**: VERIFIED | PARTIALLY VERIFIED | UNVERIFIED | CONTRADICTED
  - Evidence: <what you found>
  - Source: <URL>
- **Current coverage**: COVERED | PARTIAL | GAP
  - Where: <file:section, or "not present">
- **Recommendation**: ADOPT | ADAPT | SKIP
  - Reasoning: <1-3 sentences, specific>
  - Proposed change: <exact text + file + placement>

## Cross-Reference (if multiple documents)

<Agreement, disagreement, coverage gaps between sources.>

## Self-Review

Adjustments made:
- <item>: changed from X to Y because <reason>

Bias check: <distribution of recommendations, whether re-examination changed anything>

## Summary

| Recommendation | Count | Items |
|---------------|-------|-------|
| ADOPT | N | names |
| ADAPT | N | names |
| SKIP | N | names |

## Proposed Changes (Ready to Apply)

### <file path>
<exact text + placement>
```

## Context management

Research documents can be large (200-500 lines each) and there may be multiple. Manage your context:

- Read system files first; take notes. Don't re-read them.
- Process research documents sequentially. Extract claims to a working list, then move on.
- Cross-reference from extracted claims, not from re-reading full documents side by side.
- Build the analysis report incrementally, section by section.

## Rules

- **Assess every item.** The self-review is where filtering happens, not the initial pass.
- **Every SKIP needs a specific, defensible reason.** "Already covered" must cite the exact file and section.
- **Every ADOPT/ADAPT needs exact proposed text** with file and placement. Not "consider adding something about X."
- **Show your self-review work.** If nothing changed, explain why.
- **When sources conflict, flag it.** Don't silently pick a side.
- **Don't invent facts during validation.** If you can't verify something, say so.
