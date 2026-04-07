#!/bin/bash
# Multi-Agent Orchestrator — Adversarial Review Pipeline
#
# Calls Planner, Executor, Reviewer as separate sub-agent processes.
# Each agent runs in isolated context with its own system prompt (SKILL.md).
#
# Usage:
#   bash scripts/orchestrate.sh "Create a weekly report presentation" pptx
#   bash scripts/orchestrate.sh "Set up Datadog dashboard" datadog
#
# Requires: claude CLI (Claude Code)

set -euo pipefail

TASK="${1:?Usage: orchestrate.sh <task> <module>}"
MODULE="${2:?Usage: orchestrate.sh <task> <module>}"

MAX_RETRIES=3
MIN_SCORE=0.7
WORK_DIR="$(pwd)/.pipeline"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${WORK_DIR}/${TIMESTAMP}_${MODULE}"

mkdir -p "$RUN_DIR"

echo "=== Multi-Agent Pipeline ==="
echo "Task: $TASK"
echo "Module: $MODULE"
echo "Run dir: $RUN_DIR"
echo ""

# ─── Helper: call a sub-agent (platform-agnostic) ───
call_agent() {
  local role="$1"
  local input_file="$2"
  local output_file="$3"

  echo "  [$role] Calling sub-agent..."
  bash scripts/agents/call_agent.sh "$role" "$input_file" "$output_file" "$MODULE"
  echo "  [$role] Done → $output_file"
}

# ─── Step 1: Plan ───
echo "── Step 1: Planning ──"

cat > "$RUN_DIR/task_input.txt" <<EOF
Task: $TASK
Module: $MODULE

Generate a structured execution plan as JSON with:
- task, module, steps (each with id, action, dependencies, acceptance_criteria), risks
EOF

call_agent "planner" "$RUN_DIR/task_input.txt" "$RUN_DIR/plan.json"

# Validate plan
if [ -f "skills/planner/scripts/validate_plan.sh" ]; then
  echo "  [planner] Validating plan..."
  bash skills/planner/scripts/validate_plan.sh "$RUN_DIR/plan.json" || true
fi

echo ""

# ─── Step 2-4: Execute → Review → Retry Loop ───
ATTEMPT=0
VERDICT="needs_revision"

while [ "$ATTEMPT" -lt "$MAX_RETRIES" ] && [ "$VERDICT" != "approved" ]; do
  ATTEMPT=$((ATTEMPT + 1))
  echo "── Attempt $ATTEMPT/$MAX_RETRIES ──"

  # Build executor input
  FEEDBACK_FILE="$RUN_DIR/review_attempt_$((ATTEMPT - 1)).json"
  EXEC_INPUT="$RUN_DIR/exec_input_${ATTEMPT}.txt"

  {
    echo "PLAN:"
    cat "$RUN_DIR/plan.json"
    echo ""
    echo "ATTEMPT: $ATTEMPT of $MAX_RETRIES"
    if [ -f "$FEEDBACK_FILE" ]; then
      echo ""
      echo "PREVIOUS REVIEW FEEDBACK (address ALL issues):"
      cat "$FEEDBACK_FILE"
    fi
    echo ""
    echo "Execute the plan and produce output as JSON."
  } > "$EXEC_INPUT"

  # Execute
  call_agent "executor" "$EXEC_INPUT" "$RUN_DIR/exec_output_${ATTEMPT}.json"

  # Build reviewer input (ONLY plan + output, NO executor reasoning)
  REVIEW_INPUT="$RUN_DIR/review_input_${ATTEMPT}.txt"
  {
    echo "PLAN:"
    cat "$RUN_DIR/plan.json"
    echo ""
    echo "EXECUTION OUTPUT:"
    cat "$RUN_DIR/exec_output_${ATTEMPT}.json"
    echo ""
    echo "Module: $MODULE"
    echo ""
    echo "Review adversarially. Output JSON with: verdict, score, checklist_results, issues, suggestions"
  } > "$REVIEW_INPUT"

  # Review (isolated — no executor context)
  call_agent "reviewer" "$REVIEW_INPUT" "$RUN_DIR/review_attempt_${ATTEMPT}.json"

  # Validate review
  if [ -f "skills/reviewer/scripts/validate_review.sh" ]; then
    bash skills/reviewer/scripts/validate_review.sh "$RUN_DIR/review_attempt_${ATTEMPT}.json" || true
  fi

  # Parse verdict and score
  VERDICT=$(python3 -c "
import json, sys
try:
    with open('$RUN_DIR/review_attempt_${ATTEMPT}.json') as f:
        data = json.load(f)
    verdict = data.get('verdict', 'needs_revision')
    score = float(data.get('score', 0))
    if verdict == 'approved' and score >= $MIN_SCORE:
        print('approved')
    else:
        print('needs_revision')
except:
    print('needs_revision')
" 2>/dev/null || echo "needs_revision")

  echo "  [orchestrator] Verdict: $VERDICT"
  echo ""
done

# ─── Step 5: Result ───
echo "=== Pipeline Result ==="
if [ "$VERDICT" = "approved" ]; then
  echo "Status: SUCCESS"
  echo "Attempts: $ATTEMPT"
  echo "Final output: $RUN_DIR/exec_output_${ATTEMPT}.json"
  echo "Final review: $RUN_DIR/review_attempt_${ATTEMPT}.json"
else
  echo "Status: FAILED (max retries exhausted)"
  echo "Attempts: $ATTEMPT"
  echo "Last output: $RUN_DIR/exec_output_${ATTEMPT}.json"
  echo "Last review: $RUN_DIR/review_attempt_${ATTEMPT}.json"
  echo ""
  echo "Escalating to human review. Full history in: $RUN_DIR/"
fi

# Save summary
cat > "$RUN_DIR/summary.json" <<EOF
{
  "task": "$TASK",
  "module": "$MODULE",
  "success": $([ "$VERDICT" = "approved" ] && echo "true" || echo "false"),
  "attempts": $ATTEMPT,
  "timestamp": "$TIMESTAMP",
  "run_dir": "$RUN_DIR"
}
EOF

echo ""
echo "Summary: $RUN_DIR/summary.json"
