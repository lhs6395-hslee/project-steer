# Multi-Agent Harness — Antigravity Configuration

## Project Context

Multi-agent adversarial review pipeline with role separation.
Agents are defined as SKILL.md files in `skills/` and `modules/`.

## Standards

- Follow the pipeline: Planner → Executor → Reviewer
- Reviewer operates in adversarial mode — assume problems exist
- All inter-agent communication uses structured JSON
- Never skip the review step

## Agent Skills

Read the appropriate SKILL.md before acting in any role:
- Planner: `skills/planner/SKILL.md`
- Executor: `skills/executor/SKILL.md`
- Reviewer: `skills/reviewer/SKILL.md`
- Orchestrator: `skills/orchestrator/SKILL.md`

## Module Skills

Domain-specific: `modules/{name}/SKILL.md`
Available: pptx, docx, wbs, trello, dooray, gdrive, datadog

## Constraints

- Do NOT merge Executor and Reviewer into a single agent
- Do NOT pass Executor reasoning to the Reviewer
- Do NOT skip review, even for simple tasks
- Max 3 retry attempts before escalating to human
