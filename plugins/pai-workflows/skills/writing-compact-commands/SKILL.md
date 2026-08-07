---
name: writing-compact-commands
description: Use when the user asks for a /compact command to paste back ("write me a compact cmd", "gimme a /compact"). Flushes durable knowledge to memory first, gathers live session state with real checks, then prints one fenced /compact with summarizer directives plus a lean verbatim state block — built on the documented compaction mechanics (what re-injects from disk vs what the summary must carry).
---

# Writing Compact Commands

Produce ONE paste-ready `/compact <instructions>` command in a single fenced
code block, with **nothing after it**. The user pastes it into the harness.
Never explain the command in the reply — just print it.

## Why this shape (mechanics, verified 2026-08-07)

- `/compact [instructions]`: the harness sends a separate summarization
  request containing the FULL conversation plus your instructions as a final
  user message. The summary then **replaces** the message history. "The
  summary keeps what you choose instead of what the automatic pass guesses."
- The summarizer already sees everything — instructions **weight
  priorities**. Use a verbatim block ONLY for content that must not be
  paraphrased. Keep the whole argument ~250–500 words.
- **Never waste argument space on things that survive compaction from
  disk**: the system prompt, project-root CLAUDE.md + unscoped rules, and
  auto-memory files all re-inject automatically. LOST unless preserved:
  path-scoped rules, nested CLAUDE.md, and anything living only in message
  history. (Source: code.claude.com/docs/en/context-window,
  #what-survives-compaction.)

## Procedure

1. **Flush durable knowledge to memory FIRST.** Anything learned this
   session that matters beyond it (gotchas, decisions, project state) goes
   into auto-memory files + the MEMORY.md index before compacting — memory
   is the persistence layer and re-injects free. Then the compact argument
   only carries in-flight, session-specific state.
2. **Gather live state — actually run the checks**, don't recall from
   context: VCS branch/HEAD/dirty state, open PRs, deployed-vs-committed
   delta, in-progress tasks, running background jobs/monitors, artifact
   URLs, scratch files in use, threads blocked on the user or on external
   events. Consult project memory/CLAUDE.md for project-specific checks
   (cluster health, service state, etc.).
3. **Compose the argument** in two parts:
   - **Directive header** — PRESERVE at full fidelity: the standing
     mission; every instruction/correction/standing rule the user gave IN
     THIS SESSION (verbatim — they are not in CLAUDE.md); unresolved
     threads with exact error messages; judgment calls awaiting debate; the
     verbatim block below, unaltered. COMPRESS aggressively: raw tool
     output, resolved bugs (one-line outcome each), superseded plans,
     browsing/screenshot play-by-play. Do NOT duplicate CLAUDE.md or
     memory content — both re-inject from disk.
   - **`PRESERVE VERBATIM:` block** with tight sections:
     - MISSION — the standing intent in one or two lines.
     - NOW — in-flight work + the exact next step.
     - LIVE vs PENDING — what's deployed/running vs merely committed
       (shas, versions).
     - OPEN THREADS — each with who/what it waits on.
     - SESSION FACTS — things in no file: artifact URLs, task/run ids,
       scratch paths, where temp credentials live.
     - TRUST-FOR-DEPTH — the memory file names covering this work.
4. Print the fenced command. No prose after it.

## Anti-patterns

- A 1500-word curated megadoc as the argument: it duplicates memory's job
  and drowns the directives. Lean + directive-driven wins.
- Preserving CLAUDE.md rules or memory content in the argument (free from
  disk).
- Describing state from your own context instead of re-checking it — the
  block must reflect reality at compact time, not an hour ago.
