# Run Multi-Agent Pipeline

Execute the adversarial review pipeline with separate sub-agent processes:

1. Ask the user for the task description and target module
2. Run: `bash scripts/orchestrate.sh "<task>" <module>`
3. Each agent (Planner, Executor, Reviewer) runs as an isolated process
4. The Reviewer has NO access to Executor's reasoning
5. On failure, feedback loops back to Executor (max 3 retries)
6. Results are saved in `.pipeline/<timestamp>_<module>/`

Available modules: pptx, docx, wbs, trello, dooray, datadog, gdrive
