# Pipeline Rules

* ALL module tasks MUST go through the harness pipeline (single-agent execution forbidden)
* Evaluate Confidence_Trigger score before choosing pipeline mode
* Follow the pipeline: Confidence_Trigger → Guardian → Planner → Executor → Reviewer
* The Reviewer MUST NOT see Executor's internal reasoning — only plan + output
* Use checklist-based evaluation from the module's SKILL.md metadata
* On review failure, address ALL issues before retrying (max 3-5 per Confidence_Trigger)
* Use structured JSON for all inter-agent communication (schemas/ directory)
* All file writes use Atomic_Write pattern (tmp + mv)
* MCP servers: toggle on before task, off after completion
* Configuration flow: Claude Code → Kiro/Antigravity (one-way, never reverse)
