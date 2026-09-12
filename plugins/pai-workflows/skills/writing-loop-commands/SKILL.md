---
name: writing-loop-commands
description: Use when the user asks for a /loop command to paste back that builds a feature to completion unattended ("write me a loop cmd", "print the loop command for the next step", "give me a /loop for Tickets"). Checks that the plan file the loop will drive exists and carries a Loop protocol section (writes the section if missing), gathers the live preconditions a long unattended run needs, then prints ONE fenced /loop line — built on the documented /loop mechanics (the prompt re-enters the loop skill every tick, so it must be short and self-contained).
---

# Writing Loop Commands

Produce ONE paste-ready `/loop <prompt>` command in a single fenced code
block, with **nothing after it**. The user pastes it into the harness and
walks away. Never explain the command in the reply — just print it.

The command is deliberately tiny. All the intelligence lives in a **plan
file in the repo** that the command points at. If that plan is not ready,
this skill's job is to make it ready first (see Procedure step 1).

## Why this shape (mechanics, verified 2026-09-12)

- `/loop <prompt>` with no interval runs in **dynamic mode**: the harness
  runs the prompt now, then re-fires it via ScheduleWakeup with the
  **same prompt verbatim** every tick. The prompt is re-read on every
  wakeup and again after every context compaction, so it must be
  self-contained and short (~60–120 words). Anything longer wastes context
  on every tick.
- The prompt cannot carry per-task detail, subagent prompts, or ground
  rules — those change and would be paraphrased across compactions. They
  belong in a **plan file** the prompt names by path, with a **"Loop
  protocol"** section the orchestrator re-reads every tick. The plan file
  is the loop's state machine: `- [ ]` → `- [x]` (commit hash) is the only
  progress marker that survives everything.
- The loop ends only when the orchestrator calls ScheduleWakeup
  `stop: true`. The prompt must therefore name the **stop condition** (the
  plan's "Definition of done") and the **stop signal** (a PushNotification
  with the one-line outcome, because the user is away).
- Subagent model choice is a quota question, not a quality question. The
  orchestrator runs on the expensive model and must stay thin: it
  dispatches, verifies evidence, commits, ticks the plan. Implementers on
  opus, reviewers on sonnet, never fable/default for subagents (memory:
  `kyle-subagent-model-economy`).

## Procedure

1. **Make sure the plan the loop will drive exists and is loop-ready.**
   Look for it under `docs/superpowers/plans/` (or the project's plan dir).
   It must have every section below; write or repair whatever is missing
   before printing anything. If there is no design doc yet either, stop
   and do design → plan first (skills `writing-design-docs`,
   `superpowers:writing-plans`); a loop cannot run on a vague idea.
   - **Loop protocol** — the per-tick algorithm (template below). Pasted
     from a working build, adapted for this repo's test commands.
   - **Ground rules for implementers** — a block the orchestrator pastes
     verbatim into every implementer prompt: repo layout, test commands,
     runtime version traps, migration/topic/route registration conventions,
     "never widen scope", "never commit", report format.
   - **Tasks** — `- [ ] **Tn Title.**` items, each with the files to touch,
     the tests to write, and acceptance criteria concrete enough that a
     subagent with no conversation context can finish it. Tag UI tasks
     `[ui]` so the protocol dispatches a visual reviewer. Order by
     dependency; note which tasks are disjoint (may run in parallel).
   - **Repairs** (empty) — where the loop adds tasks when the definition of
     done fails. **Deferred** (empty) — where low/medium findings go.
   - **Definition of done** — mechanical checks: all tasks `[x]`, exact
     suite commands green, deployed and answering, live-verification
     evidence recorded. If the loop's own judgement decides "done", it
     never stops.
   - **Live verification** and **Handoff to <user>** (empty) — evidence
     tables and the commands the loop could not run itself.
2. **Gather live preconditions — actually run the checks.** A loop that
   starts on a broken baseline spends its first ticks repairing, unattended.
   Check: clean tree on the right branch; the suites green *now*; the
   subagent runtime works (spawn nothing — just confirm quota is not
   exhausted, the last 429 is behind you); any tunnels/venvs/hosts the plan's
   protocol relies on are up (see project memory for the mechanics: TCC
   workarounds, ssh forwards, python-version venvs); no other loop, monitor,
   or subagent is running (TaskList). Fix what you can; write what you
   cannot into the plan's "Handoff" so the loop routes around it.
3. **Compose the prompt** — one paragraph, no line breaks inside the fence,
   in this order:
   - the mission in five words and the role: "You are the orchestrator, not
     the coder";
   - the plan path and the instruction to follow its "Loop protocol"
     section *exactly*, every tick;
   - the tick in one sentence: first unchecked task → one opus implementer
     + sonnet reviewer(s) per the protocol → verify the test evidence
     yourself → commit → tick the box with the hash → schedule the next
     wakeup;
   - the stop rule: stop only when "Definition of done" is met, then
     PushNotification with the outcome.
   Nothing else. No task lists, no file paths beyond the plan, no rules the
   protocol already states, no restating CLAUDE.md or memory.
4. Print the fenced command. No prose after it.

## Loop protocol template (paste into the plan, adapt the commands)

```markdown
## Loop protocol (read this every tick, follow it exactly)

You are the **orchestrator**. You do not write product code yourself. You
dispatch subagents, verify their evidence, commit, and update this file.

1. Re-read this plan top to bottom. Find the first `- [ ]` task in "Tasks".
   If there is none, run "Definition of done"; if it passes, stop the loop
   (ScheduleWakeup `stop: true`) after a PushNotification with the one-line
   outcome; if it fails, add a task under "Repairs" and continue.
2. Dispatch **one opus implementer** (Agent tool, `model: "opus"`,
   `subagent_type: "general-purpose"`) with: the task text verbatim, the
   "Ground rules for implementers" block verbatim, the relevant design
   sections pasted in (not linked — the subagent has no conversation
   context), and the file paths from the task. Require TDD and a report of
   the exact test commands run with their final summary lines. Disjoint
   tasks may run in parallel; tell each implementer which paths the other
   owns.
3. When it reports, **verify the evidence yourself**: run the named test
   commands (<backend suite cmd>; <web suite cmd>). No claim of green
   without output in your own transcript.
4. Dispatch **one sonnet reviewer** (`model: "sonnet"`) with the task text,
   the design excerpt, and the uncommitted diff: defects only, ranked by
   severity, and for every guard or limit state its WORST CASE. For `[ui]`
   tasks also dispatch a **sonnet visual reviewer** that serves the built
   app against the mock API, screenshots the affected pages at 1280×800 and
   390×844 in both themes, READS the PNGs, and reports what a picky human
   would notice. Never use `model: "fable"` or the default for subagents.
5. High/critical findings go back to the same implementer via SendMessage
   (it keeps its context). Low/medium: fix if cheap, else note under
   "Deferred". At most two repair rounds per task; then mark it `- [!]`
   with a one-paragraph note and move on — never stall the whole build.
6. Hold every commit until no implementer is editing the tree (the
   pre-commit hook stashes unstaged files and races live editors). Commit
   on <branch> with `git add <file>` by name, never `-A`; message
   `feat(<area>): <task title>` + body + the session's attribution
   trailer. Then edit this file: `- [x] **Tn …** (commit `<hash>`)`.
7. Schedule the next wakeup (`delaySeconds: 60`, `noop: false`, the
   sentinel prompt the loop skill prescribes). One task per tick.
8. Quota 429 kills a subagent instantly (it wrote nothing): relaunch it.
   A "stalled" agent keeps its context: SendMessage "resume from X".
   If a Bash action is refused by the auto-mode classifier, do not retry
   variants: write the exact commands into "Handoff", PushNotification
   that the build is blocked on that step, continue with independent tasks.
   <project-specific host-access mechanics go here>
```

## Example (the Relay build, 2026-09-11)

```
/loop Build Relay to completion. You are the orchestrator, not the coder. Read docs/superpowers/plans/2026-09-11-relay-agent-messenger.md and follow its "Loop protocol" section exactly: take the first unchecked task, run it with one opus implementer subagent and sonnet reviewers as the protocol says, verify the test evidence yourself, commit on main, tick the box with the hash, then schedule the next wakeup. Stop the loop only when the plan's "Definition of done" is met, then send a PushNotification with the outcome.
```

That line ran 15 hours, 15 tasks + 2 repairs, and every task had a review
round that caught a real bug. The line never changed; the plan did.

## Anti-patterns

- A 400-word prompt with the task list inside it: it is re-sent every tick,
  paraphrased at every compaction, and drifts from the plan.
- Printing the command before the plan has a Loop protocol section: the
  orchestrator improvises a process on tick one and never recovers.
- "Done when it feels done": without a mechanical Definition of done the
  loop either stops early or never.
- Letting the orchestrator implement "just this small one": it runs on the
  expensive model and burns the quota the subagents were meant to protect.
- Committing with `git add -A` or while an implementer is still editing.
- Starting the loop on a red suite or with a tunnel down: the first tick
  becomes a repair the user did not ask for.
