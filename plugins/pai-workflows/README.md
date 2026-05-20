# pai-workflows

Workflow skills for specification work, research handling, and pre-publish content audits. Extracted from the multi-agent system behind [kyle.pericak.com](https://kyle.pericak.com)'s blog and de-personalized so you can use them on any project.

## Install

```text
/plugin marketplace add kylep/claude-plugins
/plugin install pai-workflows@pai-plugins
```

## What's in here

Seven skills. Claude Code auto-discovers them and decides when to apply each based on the description in its frontmatter — you don't typically invoke them by name.

### Specification work

| Skill | Use when… |
|---|---|
| [`writing-prds`](skills/writing-prds/SKILL.md) | A vague product idea needs scoping. Forces a structured interview (10 categories, one question at a time), then writes a PRD with verifiable acceptance criteria. |
| [`writing-design-docs`](skills/writing-design-docs/SKILL.md) | An approved PRD needs an architecture, alternatives considered, and a dependency-ordered task breakdown that feeds plan mode. |
| [`grounded-retrieval-answering`](skills/grounded-retrieval-answering/SKILL.md) | Another agent is asking interview questions and you need to answer from repo evidence with explicit confidence tiers (`[EVIDENCED]`, `[INFERRED]`, `[REASONED]`, `[BEST GUESS]`). Pairs with the two skills above for auto-interview mode. |

### Research handling

| Skill | Use when… |
|---|---|
| [`gathering-sourced-facts`](skills/gathering-sourced-facts/SKILL.md) | You're building a research brief — facts with sources and confidence levels — for a writer or another agent to use. Enforces "wide before narrow" search and primary-source preference. |
| [`synthesizing-research`](skills/synthesizing-research/SKILL.md) | Multiple research reports (e.g. Deep Research from ChatGPT + Claude + Gemini) cover the same topic and need to be folded into shared findings, unique findings, and contradictions. Uses parallel extraction subagents. |
| [`ingesting-external-research`](skills/ingesting-external-research/SKILL.md) | A research doc lands and needs validation + a triage of ADOPT / ADAPT / SKIP recommendations with reasoning you can defend. Read-only — produces a report, doesn't modify the system. |

### Content security

| Skill | Use when… |
|---|---|
| [`auditing-for-confidential-data`](skills/auditing-for-confidential-data/SKILL.md) | Content is about to ship and might contain authenticated-API output, secrets, PII, or prompt-injection vectors. Returns a pass/redact/block report. Covers OWASP LLM Top 10. |

## Design notes

**Why these specific skills?** They're the parts of my agent system that turned out to be portable — process and rubric, not infrastructure. The blog-specific orchestration, the cron pipeline, the Discord and Linear integrations all stayed home.

**Interview-driven** is a recurring pattern. `writing-prds` and `writing-design-docs` both insist on one-question-at-a-time interviews before writing anything. `grounded-retrieval-answering` exists to make that work when no human is present — a subagent answers each question from repo evidence with confidence tiers, and the pipeline keeps moving.

**Read-only research and audit** is the other pattern. `ingesting-external-research` and `auditing-for-confidential-data` both refuse to edit the system; they return a report and let you decide. Keeps the audit honest and reversible.

## License

MIT — see the [repository LICENSE](../../LICENSE).
