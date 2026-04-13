# Multi-Agent Harness — Universal Agent Instructions

## Role

You are part of a multi-agent adversarial review pipeline.
This project uses separated agent roles to prevent self-confirmation bias.

## Critical Rules

1. **Harness Mandatory**: ALL module tasks (pptx, docx, wbs, trello, dooray, gdrive, datadog) MUST go through the harness pipeline. Single-agent direct execution is FORBIDDEN.
2. **Read requirements.md first**: Evaluate Confidence_Trigger score before choosing pipeline mode.
3. **Role Isolation**: Each agent (Planner, Executor, Reviewer) operates independently
2. **Information Barrier**: The Reviewer MUST NOT see Executor's reasoning — only plan + output
3. **No Self-Review**: The agent that produces output NEVER evaluates its own work
4. **Retry with Feedback**: On review failure, Executor receives specific issues and must address ALL of them
5. **Max 3 Retries**: If Reviewer rejects 3 times, escalate to human review

## Pipeline Flow

```
1. User Request
2. Planner: Analyze → Generate structured plan with acceptance criteria
3. Executor: Follow plan → Produce concrete outputs
4. Reviewer: Adversarial check → Score (0.0–1.0) + verdict
5. If APPROVED (score >= 0.7): Return result
6. If NEEDS_REVISION: Feed issues back to Executor, retry
7. If max retries exhausted: Fail with full history
```

## Agent Skills Location

| Agent | Skill File |
|-------|-----------|
| Planner | `skills/planner/SKILL.md` |
| Executor | `skills/executor/SKILL.md` |
| Reviewer | `skills/reviewer/SKILL.md` |
| Orchestrator | `skills/orchestrator/SKILL.md` |

## Module Skills

Domain-specific knowledge in `modules/{name}/SKILL.md`:
- pptx, docx, wbs, trello, dooray, gdrive, datadog

Each module defines its own review checklist in YAML frontmatter `metadata.checklist`.

## Preferences

- Use structured JSON for all inter-agent communication
- Always include acceptance criteria in plans
- Reviewer must use checklist-based evaluation
- Log all attempts and feedback for debugging

## Constraints

- Do NOT merge Executor and Reviewer into a single agent
- Do NOT pass Executor's internal reasoning to the Reviewer
- Do NOT skip the review step, even for "simple" tasks

## Execution

Primary platform: Claude Code (`claude --print` sub-agents)

```bash
bash scripts/orchestrate.sh "<task>" <module>
```

MCP toggle (updates both Claude Code and Kiro configs):
```bash
bash scripts/mcp-toggle.sh status
bash scripts/mcp-toggle.sh <server> on|off
```

## Cross-Platform

Configuration flow is one-way: Claude Code → Kiro/Antigravity (never reverse).

| Platform | Config Files | Pipeline Entry |
|----------|-------------|----------------|
| Claude Code (Primary) | `CLAUDE.md`, `.mcp.json` | `bash scripts/orchestrate.sh` |
| Kiro (Sync) | `.kiro/steering/`, `.kiro/hooks/`, `.kiro/settings/mcp.json` | Hook: "Run Multi-Agent Pipeline" |
| Antigravity (Sync) | `.gemini/GEMINI.md`, `.agent/rules/`, `.agent/workflows/` | Workflow: `/run-pipeline` |

Sync: `bash scripts/mcp-toggle.sh sync` (Claude Code → Kiro one-way)
