---
name: grounded-retrieval-answering
description: Use when answering interview-style questions from another agent (PRD writer, design doc writer, planner) by searching the repo — wiki, codebase, agent definitions, prior docs — and returning an answer with explicit confidence tiers. Always produces an answer; never refuses for lack of evidence.
---

# Grounded Retrieval Answering

Answer questions from another agent by searching the repository for evidence and producing an answer tagged with confidence tiers. **Always answer.** Never refuse, never stop with "insufficient evidence." The tier system makes quality transparent without stopping the pipeline.

## When to use

- A PRD writer or design doc writer in auto-interview mode is asking you a question
- A planner needs a grounded answer about the system to fill in a plan
- Any caller wants an answer-from-repo with explicit confidence labels

## When NOT to use

- Web research is required — this skill is repo-only by design
- The caller wants a free-form opinion — go ahead and answer normally
- The user is a human asking interactively — talk to them directly

## Confidence tiers

Every answer is tagged with one of these tiers. An answer can mix tiers.

| Tier | Tag | When to use |
|------|-----|-------------|
| 1 | `[EVIDENCED]` | Direct source in the repo answers the question |
| 2 | `[INFERRED]` | A pattern in existing docs / code applies to this case |
| 3 | `[REASONED]` | Deduced from the stack contract + known constraints |
| 4 | `[BEST GUESS]` | No repo evidence, but you can reason about what would be valuable given the stack and the user's patterns |

Example mixed answer:

> "We use Vault for secrets `[EVIDENCED]`. This new tool would need a Vault integration for API key storage `[REASONED]`. The tool's Prometheus exporter would be useful since metrics coverage is thin today `[BEST GUESS]`."

## Retrieval strategy

Follow this order for every question:

1. **Stack contract first.** Read the project's stack contract / architecture overview if one exists (look for `stack-contract.md`, `architecture.md`, `ADRs/`). This has canonical facts.

2. **Keyword search.** Extract 2-4 keywords from the question. Grep across:
   - The project wiki / docs
   - Infrastructure dirs (Helm, k8s manifests, Terraform, scripts — ground truth)
   - Agent / skill / command definitions
   - Existing PRDs and design docs

3. **Triage candidates.** For long wiki pages, read the frontmatter (first 15 lines) to check title/summary/keywords/scope for relevance before deep reads.

4. **Deep read.** Read the full content of the 2-5 most relevant sources. **Code files are first-class evidence** — often more authoritative than wiki pages.

5. **Supplementary check.** If the question touches conventions or rules, also read `CLAUDE.md` / `AGENTS.md` at the repo root.

6. **Synthesize.** Compose your answer with tiers and citations.

## Output format

```
## Answer

<answer text with [TIER] tags and inline source citations>

## Sources

- <file path> — <what was found here>
- <file path> — <what was found here>

## Confidence notes

- <what parts are EVIDENCED vs INFERRED vs REASONED vs BEST GUESS, and why>
```

## Rules (non-negotiable)

- **Always answer.** If you find zero evidence, use `[BEST GUESS]` and reason from the stack and the user's patterns. A best guess is better than no answer.
- **Cite file paths.** Every `[EVIDENCED]` or `[INFERRED]` claim cites a source file. `[REASONED]` cites the stack contract or convention it's based on. `[BEST GUESS]` explains the reasoning.
- **Code is evidence.** Helm values files, Dockerfiles, k8s manifests, and agent definitions are first-class sources. Don't treat only docs as evidence.
- **Be specific.** "We use Vault" is less useful than "Vault with GCP KMS auto-unseal, secrets delivered via Vault Agent Injector (Source: `infra/vault/values.yaml`)."
- **Flag gaps honestly.** If a question is partially covered, say what you found and what's missing. Don't pad thin evidence into a confident-sounding answer.
- **Don't search the web.** This skill is repo-only. If external research is needed, say so in confidence notes — the calling agent's research phase handles it.
- **Read-only.** Never write files, run commands, or modify anything.
