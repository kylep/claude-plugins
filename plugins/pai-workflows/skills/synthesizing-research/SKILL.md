---
name: synthesizing-research
description: Use when comparing or contrasting multiple research reports on the same topic (e.g. Deep Research outputs from ChatGPT, Claude, and Gemini) into a single structured summary with shared findings, unique findings, and contradictions.
---

# Synthesizing Research

Compare and contrast multiple research reports on the same topic into a structured compare-and-contrast document. Add nothing from outside the source material — no opinions, no external knowledge, no editorializing.

## When to use

- Multiple Deep Research providers were run on the same prompt and the user wants a single rolled-up view
- Two or more analyst reports cover the same domain and need a cross-source summary
- You need to know what claims have multiple-source support vs. single-source support vs. contradicted positions

## When NOT to use

- Only one source — there's nothing to synthesize, just summarize
- The sources cover different topics — synthesis assumes a shared subject
- The user wants a recommendation, not a comparison — synthesis is neutral by definition

## Input

A directory containing:
- One `.md` file per source (e.g. `chatgpt.md`, `claude.md`, `gemini.md`)
- Optionally an `index.md` describing the prompt and listing the reports

## Workflow

### 1. Discover source files

Glob `<dir>/*.md` and identify the sources (everything except `index.md` if present). Note the count — you'll spawn one extraction subagent per source.

### 2. Extract findings (parallel agents)

Spawn one extraction subagent per source, all in a single message (parallel). Each agent's prompt:

> Read `<filepath>` thoroughly. Extract every distinct piece of advice, recommendation, technique, finding, or insight. Return a comprehensive bullet list — one bullet per distinct point. Include enough detail per bullet that someone could act on it without reading the original. Label this as "Source: `<filename without extension>`".

### 3. Categorize

With all extractions in hand, categorize every point:

- **Shared Findings** — present in 2+ sources. Tag each with which sources agree (e.g. "all 3" or "ChatGPT, Claude"). Bold the key concept. Sort: all-N items first, then progressively fewer.
- **Unique Findings** — present in only one source. Group by source under H4 subheadings. Bold the key concept.
- **Contradictions** — points where sources actively disagree or prescribe conflicting approaches. Bold the topic. Describe each source's position without picking a side.

### 4. Write output

Write the synthesis to `index.md` (or wherever the user specifies). If a `## Cross-Source Synthesis` section exists, replace it. Otherwise append after the reports list.

```markdown
---

## Cross-Source Synthesis

<1-2 sentence intro stating this is a compare/contrast with no outside opinions.>

### Shared Findings (present in 2+ sources)

- **Bold key concept** — description (source tags)
...

### Unique Findings (from one source only)

#### <Source 1> only
- ...

#### <Source 2> only
- ...

### Contradictions (points where sources disagree)

- **Bold topic** — describe each source's position
...
```

## Rules

- **Extract and report all findings.** Do not pre-filter or editorialize.
- **Never add claims, context, or knowledge from outside the source files.**
- **Never pick sides in contradictions.** State each position neutrally.
- **Bold the key concept** in each bullet for scannability.
- **Tag shared findings** with which sources agree.
- If a point is close but sources frame it differently, it's shared only if the core advice is the same. If the framing difference is substantive, it's a contradiction.

## Why parallel extraction

Sources can be long (200-500 lines each). Reading them sequentially into your own context wastes tokens and risks context pollution. Parallel extraction subagents each see only one source, return a structured bullet list, and you synthesize from the lists — never from the full source text.
