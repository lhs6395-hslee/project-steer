#!/bin/bash
# Multi-Agent Orchestrator — Full Harness Pipeline
#
# Integrates all 23 requirements from ai-agent-engineering-spec-2026:
#   Confidence_Trigger → Guardian → Planner (UltraPlan) → Generator → Evaluator
#   + IDE_Adapter + Token Tracking + Feedback_Loop + Agent_Team
#
# Usage:
#   bash scripts/orchestrate.sh "Create a weekly report presentation" pptx
#   bash scripts/orchestrate.sh "Set up Datadog dashboard" datadog
#   bash scripts/orchestrate.sh "주간 보고 생성" "pptx,dooray,trello"  # Agent_Team

set -euo pipefail

# ── Load IDE Adapter ──
source "$(dirname "$0")/agents/ide_adapter.sh"
ensure_agent_dirs

TASK="${1:?Usage: orchestrate.sh <task> <module(s)>}"
MODULES="${2:?Usage: orchestrate.sh <task> <module(s)>}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$AGENT_DIR/${TIMESTAMP}_${MODULES//,/_}"

mkdir -p "$RUN_DIR"

echo "=== Multi-Agent Harness Pipeline ==="
echo "IDE: $IDE_NAME"
echo "Task: $TASK"
echo "Module(s): $MODULES"
echo "Run dir: $RUN_DIR"
echo ""

# ── Step 0: Confidence_Trigger ──
echo "── Step 0: Confidence_Trigger ──"
CT_RESULT=$(bash scripts/agents/confidence_trigger.sh "$TASK" "${MODULES%%,*}")
echo "$CT_RESULT" | tee "$RUN_DIR/confidence_trigger.json"

MODE=$(echo "$CT_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['mode'])")
MAX_RETRIES=$(echo "$CT_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['max_retries'])")
ULTRAPLAN=$(echo "$CT_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['ultraplan'])")

echo "  Mode: $MODE | Max retries: $MAX_RETRIES | UltraPlan: $ULTRAPLAN"
echo ""

# ── Single agent mode — skip pipeline ──
if [ "$MODE" = "single" ]; then
  echo "Confidence score >= 0.85 — single agent mode. No pipeline needed."
  SINGLE_TASK="$TASK" python3 -c "import json,os; print(json.dumps({'mode':'single','task':os.environ['SINGLE_TASK'],'result':'direct_execution'}, ensure_ascii=False))" | { read -r content; atomic_write "$RUN_DIR/summary.json" "$content"; }
  exit 0
fi

# ── Agent_Team mode (multiple modules) ──
if [[ "$MODULES" == *","* ]]; then
  echo "── Agent_Team mode: multiple modules detected ──"
  bash scripts/agents/agent_team.sh "$TASK" "$MODULES"
  exit $?
fi

MODULE="$MODULES"

# ── Step 0.5: MCP Toggle ──
echo "── Step 0.5: MCP Toggle ──"
bash scripts/mcp-toggle.sh "$MODULE" on 2>/dev/null || echo "  MCP toggle skipped (server not found)"
echo ""

# ── Step 1: UltraPlan (if needed) ──
if [ "$ULTRAPLAN" = "True" ]; then
  echo "── Step 1: UltraPlan ──"
  bash scripts/agents/ultraplan.sh "$TASK" "$MODULE"
  echo ""
fi

# ── Step 2: Plan ──
echo "── Step 2: Planning ──"
PLAN_INPUT="$RUN_DIR/plan_input.txt"
cat > "$PLAN_INPUT" <<EOF
Task: $TASK
Module: $MODULE
Mode: $MODE
Max retries: $MAX_RETRIES

Generate a Sprint_Contract JSON following schemas/sprint_contract.schema.json.
Include acceptance_criteria, constraints, risks.
EOF

PLAN_OUTPUT="$RUN_DIR/sprint_contract.json"
bash scripts/agents/call_agent.sh planner "$PLAN_INPUT" "$PLAN_OUTPUT" "$MODULE"

# Validate plan
if [ -f "skills/planner/scripts/validate_plan.sh" ]; then
  bash skills/planner/scripts/validate_plan.sh "$PLAN_OUTPUT" || true
fi
echo ""

# ── Step 3-5: Execute → Review → Retry Loop ──
ATTEMPT=0
VERDICT="needs_revision"
OUTPUT=""
REVIEW=""

while [ "$ATTEMPT" -lt "$MAX_RETRIES" ] && [ "$VERDICT" != "approved" ] && [ "$VERDICT" != "pass" ]; do
  ATTEMPT=$((ATTEMPT + 1))
  echo "── Attempt $ATTEMPT/$MAX_RETRIES ──"

  # ── Guardian check ──
  echo "  [Guardian] Pre-execution safety check..."
  GUARDIAN_TASK="$TASK" python3 -c "import json,os; print(json.dumps({'tool_input':{'command':os.environ['GUARDIAN_TASK']}}))" | bash scripts/agents/guardian.sh || {
    EXIT_CODE=$?
    if [ "$EXIT_CODE" -eq 2 ]; then
      echo "  [Guardian] BLOCKED — aborting pipeline"
      echo '{"status":"blocked","reason":"guardian"}' > "$RUN_DIR/summary.json"
      bash scripts/mcp-toggle.sh "$MODULE" off 2>/dev/null || true
      exit 2
    fi
  }

  # ── Execute ──
  EXEC_INPUT="$RUN_DIR/exec_input_${ATTEMPT}.txt"
  EXEC_OUTPUT="$RUN_DIR/exec_output_${ATTEMPT}.json"
  FEEDBACK_FILE="$RUN_DIR/verdict_$((ATTEMPT-1)).json"

  {
    echo "SPRINT_CONTRACT:"
    cat "$PLAN_OUTPUT"
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

  bash scripts/agents/call_agent.sh executor "$EXEC_INPUT" "$EXEC_OUTPUT" "$MODULE"

  # ── KAIROS quick check ──
  echo "  [KAIROS] Quick lint check..."
  bash scripts/agents/kairos.sh "$EXEC_OUTPUT" 2>/dev/null || true

  # ── Review (isolated — no executor context) ──
  REVIEW_INPUT="$RUN_DIR/review_input_${ATTEMPT}.txt"
  VERDICT_FILE="$RUN_DIR/verdict_${ATTEMPT}.json"

  {
    echo "SPRINT_CONTRACT:"
    cat "$PLAN_OUTPUT"
    echo ""
    echo "EXECUTION OUTPUT:"
    cat "$EXEC_OUTPUT"
    echo ""
    echo "Module: $MODULE"
    echo "Review adversarially. Output JSON verdict following schemas/verdict.schema.json."
  } > "$REVIEW_INPUT"

  bash scripts/agents/call_agent.sh reviewer "$REVIEW_INPUT" "$VERDICT_FILE" "$MODULE"

  # Validate review
  if [ -f "skills/reviewer/scripts/validate_review.sh" ]; then
    bash skills/reviewer/scripts/validate_review.sh "$VERDICT_FILE" || true
  fi

  # Parse verdict
  VERDICT=$(python3 -c "
import json, sys
try:
    with open('$VERDICT_FILE') as f:
        data = json.load(f)
    v = data.get('verdict', data.get('overall_status', 'needs_revision'))
    s = float(data.get('score', 0))
    if v in ('approved', 'pass') and s >= 0.7:
        print('approved')
    else:
        print('needs_revision')
except:
    print('needs_revision')
" 2>/dev/null || echo "needs_revision")

  echo "  [Orchestrator] Verdict: $VERDICT (attempt $ATTEMPT)"

  # ── Circular feedback detection ──
  if [ "$ATTEMPT" -ge 2 ]; then
    PREV_ISSUES=$(python3 -c "import json; print(json.load(open('$RUN_DIR/verdict_$((ATTEMPT-1)).json')).get('issues',['']))" 2>/dev/null || echo "")
    CURR_ISSUES=$(python3 -c "import json; print(json.load(open('$VERDICT_FILE')).get('issues',['']))" 2>/dev/null || echo "")
    if [ "$PREV_ISSUES" = "$CURR_ISSUES" ] && [ -n "$PREV_ISSUES" ]; then
      echo "  [Orchestrator] ⚠️ Circular feedback detected — same issues across attempts. Escalating."
      VERDICT="escalated"
      break
    fi
  fi

  echo ""
done

# ── Step 6: Token tracking ──
echo "── Token Report ──"
bash scripts/agents/token_tracker.sh "$RUN_DIR" 2>/dev/null || echo "  Token tracking skipped"

# ── Step 7: MCP off ──
bash scripts/mcp-toggle.sh "$MODULE" off 2>/dev/null || true

# ── Step 8: Result ──
echo ""
echo "=== Pipeline Result ==="
if [ "$VERDICT" = "approved" ]; then
  echo "Status: SUCCESS"
elif [ "$VERDICT" = "escalated" ]; then
  echo "Status: ESCALATED (circular feedback — human review needed)"
else
  echo "Status: FAILED (max retries exhausted)"
fi

echo "Attempts: $ATTEMPT"
echo "Run dir: $RUN_DIR"

# Save summary
export TASK MODULE MODE VERDICT ATTEMPT MAX_RETRIES ULTRAPLAN TIMESTAMP RUN_DIR
atomic_write "$RUN_DIR/summary.json" "$(python3 -c "
import json, os
print(json.dumps({
    'task': os.environ['TASK'],
    'module': os.environ['MODULE'],
    'mode': os.environ['MODE'],
    'success': os.environ['VERDICT'] == 'approved',
    'verdict': os.environ['VERDICT'],
    'attempts': int(os.environ['ATTEMPT']),
    'max_retries': int(os.environ['MAX_RETRIES']),
    'ultraplan': os.environ['ULTRAPLAN'] == 'True',
    'timestamp': os.environ['TIMESTAMP'],
    'run_dir': os.environ['RUN_DIR']
}, ensure_ascii=False, indent=2))
")"
