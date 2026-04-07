# Run Adversarial Review

Execute a full adversarial review on the latest execution output:

1. Load the relevant module's SKILL.md and extract the checklist
2. Read the execution plan and output
3. Evaluate each checklist criterion independently
4. Score from 0.0 to 1.0
5. Provide verdict: approved, needs_revision, or rejected
6. List all issues with specific, actionable descriptions
7. Output as structured JSON
