#!/bin/bash
# Multi-Agent Orchestrator — Harness Pipeline v2.1
#
# v2.1 Changes (공식 문서 근거):
#   - --json-schema로 Planner/Executor/Reviewer 구조화 출력 강제
#     (code.claude.com/docs/en/cli-reference.md)
#   - extract_result.py: structured_output 필드 우선 추출, fallback wrapping 제거
#     (code.claude.com/docs/en/agent-sdk/structured-outputs.md)
#   - Executor 출력에 constraint_compliance 필수 (schemas/executor_output.schema.json)
#   - Reviewer 출력에 constraint_violations, retry_fix_assessment 필수
#     (schemas/verdict.schema.json v2.0)
#
# Official docs references:
#   - CLI Reference: code.claude.com/docs/en/cli-reference.md
#   - Structured Outputs: code.claude.com/docs/en/agent-sdk/structured-outputs.md
#   - Headless Mode: code.claude.com/docs/en/headless.md
#   - Subagents: code.claude.com/docs/en/agent-sdk/subagents.md
#
# Usage:
#   bash scripts/orchestrate.sh "Create a weekly report presentation" pptx
#   bash scripts/orchestrate.sh "주간 보고 생성" "pptx,dooray,trello"  # Agent_Team

set -euo pipefail

# ── Load IDE Adapter ──
source "$(dirname "$0")/agents/ide_adapter.sh"
ensure_agent_dirs

TASK="${1:?Usage: orchestrate.sh <task> <module(s)>}"
MODULES="${2:?Usage: orchestrate.sh <task> <module(s)>}"

# ── 모듈명 유효성 검증 ──
VALID_MODULES="pptx docx wbs trello dooray gdrive datadog"
IFS=',' read -ra MOD_LIST <<< "$MODULES"
for mod in "${MOD_LIST[@]}"; do
  mod=$(echo "$mod" | tr -d ' ')
  if ! echo "$VALID_MODULES" | grep -qw "$mod"; then
    echo "ERROR: Invalid module '$mod'. Valid: $VALID_MODULES"
    exit 1
  fi
done

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$AGENT_DIR/${TIMESTAMP}_${MODULES//,/_}"

mkdir -p "$RUN_DIR"

# ── Create initial Handoff_File ──
echo "$$" > "$AGENT_DIR/running.lock"
HANDOFF_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
HANDOFF_FILE="$AGENT_DIR/requests/${TIMESTAMP}_orchestrator_request.json"
export HANDOFF_ID TASK MODULES TIMESTAMP
HANDOFF_CONTENT=$(python3 <<'PYEOF'
import json, os
print(json.dumps({
    'id': os.environ['HANDOFF_ID'],
    'timestamp': os.environ['TIMESTAMP'],
    'from_agent': 'orchestrator',
    'to_agent': 'planner',
    'status': 'pending',
    'iteration': 0,
    'payload': {
        'task': os.environ['TASK'],
        'modules': os.environ['MODULES']
    }
}, ensure_ascii=False, indent=2))
PYEOF
)
atomic_write "$HANDOFF_FILE" "$HANDOFF_CONTENT"

echo "=== Multi-Agent Harness Pipeline v2.1 (--json-schema) ==="
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
echo "── Step 2: Planning (--json-schema: sprint_contract) ──"
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
if ! bash scripts/agents/call_agent.sh planner "$PLAN_INPUT" "$PLAN_OUTPUT" "$MODULE"; then
  echo "FAIL: Planner agent failed"
  exit 1
fi

if [ ! -s "$PLAN_OUTPUT" ]; then
  echo "FAIL: Sprint_Contract empty"
  exit 1
fi

# Validate plan
if [ -f "skills/planner/scripts/validate_plan.sh" ]; then
  bash skills/planner/scripts/validate_plan.sh "$PLAN_OUTPUT" || true
fi

# ── Plan Transparency (Anthropic trustworthy-agents 2026-04-09) ──
# "Plan Mode: users review and authorize the complete plan before execution"
# "shifts oversight from the individual step to the overall strategy"
# PLAN_REVIEW=1 env로 활성화 (CI/자동화 환경에서는 생략)
if [ "${PLAN_REVIEW:-0}" = "1" ]; then
  echo "── Sprint_Contract (review before execution) ──"
  python3 -c "
import json, sys
with open('$PLAN_OUTPUT') as f: p = json.load(f)
print(f\"Task: {p.get('task','')}\")
print(f\"Steps ({len(p.get('steps',[]))}):\" )
for s in p.get('steps',[]): print(f\"  [{s.get('id')}] {s.get('action','')} [{s.get('estimated_complexity','')}]\")
print(f\"Constraints: {len(p.get('constraints',[]))} | Risks: {len(p.get('risks',[]))}\")
"
  echo ""
  printf "Proceed with execution? [Y/n] "
  read -r CONFIRM
  if [[ "${CONFIRM,,}" == "n" ]]; then
    echo "Execution cancelled by user (Plan Review)"
    exit 0
  fi
fi
echo ""

# ── Step 3-5: Execute → Review → Retry Loop ──
ATTEMPT=0
VERDICT="needs_revision"

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

  # ── Execute (--json-schema: executor_output) ──
  echo "  [Executor] Running with --json-schema (constraint_compliance enforced)..."
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
    echo "Execute the plan and produce output as JSON matching schemas/executor_output.schema.json."
    echo "REQUIRED fields: constraint_compliance, outputs, status, artifacts."
    if [ "$ATTEMPT" -gt 1 ]; then
      echo "REQUIRED on retry: retry_fixes field with issue + fix_applied + verified for EACH previous issue."
    fi
  } > "$EXEC_INPUT"

  # ── Parallel Execution (dependency-aware) ──
  echo "  [Executor] Running in parallel mode (dependency-aware)..."
  python3 scripts/agents/parallel_executor.py "$PLAN_OUTPUT" "$MODULE" "$RUN_DIR"

  # Use aggregated output from parallel execution
  PARALLEL_OUTPUT="$RUN_DIR/aggregated_output.json"
  if [ -f "$PARALLEL_OUTPUT" ]; then
    cp "$PARALLEL_OUTPUT" "$EXEC_OUTPUT"
  else
    echo "ERROR: Parallel execution failed - no aggregated output"
    exit 1
  fi

  # ── KAIROS quick check ──
  echo "  [KAIROS] Quick lint check..."
  bash scripts/agents/kairos.sh "$EXEC_OUTPUT" 2>/dev/null || true

  # ── Review (parallel — per-step, information isolated) ──
  # INFORMATION BARRIER: each Reviewer gets ONLY Sprint_Contract + its own step output
  # 공식 근거: code.claude.com/docs/en/agent-sdk/subagents.md
  #   "run style-checker, security-scanner, test-coverage simultaneously"
  echo "  [Reviewer] Running parallel per-step review (information isolated)..."
  VERDICT_FILE="$RUN_DIR/verdict_${ATTEMPT}.json"

  python3 scripts/agents/parallel_reviewer.py \
    "$PLAN_OUTPUT" "$EXEC_OUTPUT" "$MODULE" "$RUN_DIR" "$ATTEMPT" || true

  if [ ! -f "$VERDICT_FILE" ]; then
    echo "  WARNING: parallel_reviewer produced no verdict — falling back to single reviewer"
    REVIEW_INPUT="$RUN_DIR/review_input_${ATTEMPT}.txt"
    {
      echo "SPRINT_CONTRACT:"; cat "$PLAN_OUTPUT"
      echo ""; echo "EXECUTION OUTPUT:"; cat "$EXEC_OUTPUT"
      echo ""; echo "Module: $MODULE"; echo "Attempt: $ATTEMPT"
      echo "Review adversarially. Output JSON verdict following schemas/verdict.schema.json."
      echo "REQUIRED: checklist_results, constraint_violations, issues, suggestions."
    } > "$REVIEW_INPUT"
    bash scripts/agents/call_agent.sh reviewer "$REVIEW_INPUT" "$VERDICT_FILE" "$MODULE"
  fi

  # Parse verdict (v2.1 — constraint_violations aware)
  # 공식 근거: schemas/verdict.schema.json (v2.0 — Constraint Verification)
  VERDICT=$(python3 -c "
import json, sys
try:
    with open('$VERDICT_FILE') as f:
        data = json.load(f)
    v = data.get('verdict', data.get('overall_status', 'needs_revision'))
    s = float(data.get('score', 0))
    # v2.1: constraint_violations가 있으면 자동 실패
    violations = data.get('constraint_violations', [])
    if violations:
        print('needs_revision')
    elif v in ('approved', 'pass') and s >= 0.7:
        print('approved')
    else:
        print('needs_revision')
except:
    print('needs_revision')
" 2>/dev/null || echo "needs_revision")

  SCORE=$(python3 -c "
import json
try:
    with open('$VERDICT_FILE') as f:
        print(json.load(f).get('score', 0))
except:
    print(0)
" 2>/dev/null || echo "0")

  echo "  [Orchestrator] Verdict: $VERDICT | Score: $SCORE (attempt $ATTEMPT)"

  # ── Circular feedback detection ──
  if [ "$ATTEMPT" -ge 2 ]; then
    CIRCULAR=$(python3 -c "
import json, sys
try:
    with open('$RUN_DIR/verdict_$((ATTEMPT-1)).json') as f:
        prev = json.load(f)
    with open('$VERDICT_FILE') as f:
        curr = json.load(f)
    prev_issues = sorted(prev.get('issues', []))
    curr_issues = sorted(curr.get('issues', []))
    if prev_issues == curr_issues and len(curr_issues) > 0:
        print('yes')
    else:
        print('no')
except:
    print('no')
" 2>/dev/null)
    if [ "$CIRCULAR" = "yes" ]; then
      echo "  [Orchestrator] Circular feedback detected — same issues across attempts. Escalating."
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

# ── Remove pipeline lock ──
rm -f "$AGENT_DIR/running.lock"

export TASK MODULE MODE VERDICT ATTEMPT MAX_RETRIES ULTRAPLAN TIMESTAMP RUN_DIR
SUMMARY_CONTENT=$(python3 <<'PYEOF'
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
PYEOF
)
atomic_write "$RUN_DIR/summary.json" "$SUMMARY_CONTENT"
