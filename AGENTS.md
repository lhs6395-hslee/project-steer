# Multi-Agent Harness — Universal Agent Instructions

## Role

You are part of a multi-agent adversarial review pipeline implementing 23 requirements from ai-agent-engineering-spec-2026.

## Critical Rules

1. **Harness Mandatory**: ALL module tasks (pptx, docx, wbs, trello, dooray, gdrive, datadog) MUST go through the harness pipeline. Single-agent direct execution is FORBIDDEN.
2. **Read requirements.md first**: Evaluate Confidence_Trigger score before choosing pipeline mode.
3. **Role Isolation**: Each agent (Planner, Executor, Reviewer) operates independently
4. **Information Barrier**: The Reviewer MUST NOT see Executor's reasoning — only plan + output
5. **No Self-Review**: The agent that produces output NEVER evaluates its own work
6. **Retry with Feedback**: On review failure, Executor receives specific issues and must address ALL of them
7. **Max 3-5 Retries**: Confidence_Trigger 구간에 따라 3~5회. 초과 시 escalate to human review
8. **Atomic_Write**: All file writes use atomic pattern (tmp + mv)

## Pipeline Flow

```
1. Confidence_Trigger: Evaluate task risk/complexity → determine mode
2. Guardian: Pre-execution safety check (Pattern_Matcher, no API call)
3. Planner: Analyze → Generate Sprint_Contract (schemas/sprint_contract.schema.json)
4. Executor: Follow plan → Produce outputs
5. Reviewer: Adversarial check → Verdict (schemas/verdict.schema.json)
6. If APPROVED (score >= 0.7): Return result
7. If NEEDS_REVISION: Feed issues back to Executor, retry
8. Token tracking + MCP off
```

## Confidence_Trigger

| Score | Mode | Max Retries | UltraPlan |
|-------|------|-------------|-----------|
| ≥0.85 | Single agent | N/A | Off |
| 0.70-0.84 | Multi (reduced) | 3 | Off |
| 0.50-0.69 | Multi (full) | 5 | Off |
| <0.50 | Multi + UltraPlan | 5 | On |

## Execution

Primary platform: Claude Code (`claude --print` sub-agents)

```bash
bash scripts/orchestrate.sh "<task>" <module>
bash scripts/orchestrate.sh "<task>" "mod1,mod2"  # Agent_Team
bash scripts/mcp-toggle.sh <server> on|off
bash scripts/agents/sync_pipeline.sh --from claude_code --to all
```

## Agent Scripts (23 Requirements)

| Script | Role | Req |
|--------|------|-----|
| orchestrate.sh | Pipeline orchestrator | R1 |
| call_agent.sh | Sub-agent caller (claude/gemini) | R7,R10 |
| confidence_trigger.sh | Risk/complexity scoring | R13 |
| guardian.sh | Dangerous command blocker | R5 |
| ide_adapter.sh | Runtime IDE detection | R15 |
| kairos.sh | Lightweight lint monitor | R19 |
| auto_dream.sh | Memory cleanup | R18 |
| ultraplan.sh | Hierarchical task decomposition | R20 |
| token_tracker.sh | Cost/token management | R14 |
| harness_subtraction.sh | Optimization analysis | R23 |
| agent_team.sh | Multi-module coordination | R22 |
| git_worktree.sh | Parallel execution | R17 |
| sdd_integrator.sh | Spec-driven development | R21 |
| sync_pipeline.sh | Cross-IDE sync | R16 |

## Cross-Platform

Configuration flow is one-way: Claude Code → Kiro/Antigravity (never reverse).

| Platform | Config Files | Pipeline Entry |
|----------|-------------|----------------|
| Claude Code (Primary) | `CLAUDE.md`, `.mcp.json`, `.claude/settings.json` | `bash scripts/orchestrate.sh` |
| Kiro (Sync) | `.kiro/steering/`, `.kiro/hooks/`, `.kiro/settings/mcp.json` | `invokeSubAgent` + Hook |
| Antigravity (Sync) | `.gemini/GEMINI.md`, `.agent/rules/`, `.agent/workflows/` | Workflow: `/run-pipeline` |

Sync: `bash scripts/agents/sync_pipeline.sh --from claude_code --to all`

## Constraints

- Do NOT merge Executor and Reviewer into a single agent
- Do NOT pass Executor's internal reasoning to the Reviewer
- Do NOT skip the review step, even for "simple" tasks
- Do NOT write files without Atomic_Write pattern
