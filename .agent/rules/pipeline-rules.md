# Pipeline Rules

* Follow the adversarial review pipeline: Planner → Executor → Reviewer
* The Reviewer MUST NOT see Executor's internal reasoning — only plan + output
* Always include acceptance criteria in execution plans
* Use checklist-based evaluation from the module's SKILL.md metadata
* On review failure, address ALL issues before retrying
* Maximum 3 retry attempts before escalating to human review
* Use structured JSON for all inter-agent communication
