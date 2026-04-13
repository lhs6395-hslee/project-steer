#!/bin/bash
# Agent_Team — 전문화된 에이전트 팀 협업
# Coordinator가 Specialist 에이전트들의 작업을 분배하고 통합
#
# Usage: bash scripts/agents/agent_team.sh "<task>" "<modules_csv>"
# Example: bash scripts/agents/agent_team.sh "주간 보고 생성" "pptx,dooray,trello"

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in agent_team.sh (line $LINENO)" >&2; exit 2' ERR

source "$(dirname "$0")/ide_adapter.sh"
ensure_agent_dirs

TASK="${1:?Usage: agent_team.sh <task> <modules_csv>}"
MODULES="${2:?Usage: agent_team.sh <task> <modules_csv>}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

echo "=== Agent Team — Coordinator ==="
echo "Task: $TASK"
echo "Modules: $MODULES"

IFS=',' read -ra MODULE_LIST <<< "$MODULES"

# ── Step 1: 각 모듈별 Sprint_Contract 생성 (Planner) ──
echo ""
echo "── Step 1: Planning per module ──"
for mod in "${MODULE_LIST[@]}"; do
  mod=$(echo "$mod" | tr -d ' ')
  echo "  [Planner] Module: $mod"
  INPUT_FILE="$AGENT_DIR/requests/${TIMESTAMP}_team_${mod}_input.txt"
  CONTRACT_FILE="$AGENT_DIR/contracts/${TIMESTAMP}_team_${mod}_contract.json"

  cat > "$INPUT_FILE" <<EOF
Task: $TASK
Module: $mod
Context: This is part of an Agent_Team execution. Focus only on the $mod module scope.
Generate a Sprint_Contract JSON following schemas/sprint_contract.schema.json.
EOF

  bash scripts/agents/call_agent.sh planner "$INPUT_FILE" "$CONTRACT_FILE" "$mod"
done

# ── Step 2: 독립 모듈은 병렬 실행 (& 백그라운드 + wait) ──
echo ""
echo "── Step 2: Executing per module (parallel) ──"
EXEC_PIDS=()
for mod in "${MODULE_LIST[@]}"; do
  mod=$(echo "$mod" | tr -d ' ')
  echo "  [Executor] Module: $mod (background)"
  CONTRACT_FILE="$AGENT_DIR/contracts/${TIMESTAMP}_team_${mod}_contract.json"
  OUTPUT_FILE="$AGENT_DIR/outputs/${TIMESTAMP}_team_${mod}_output.json"

  if [ -f "$CONTRACT_FILE" ]; then
    bash scripts/agents/call_agent.sh executor "$CONTRACT_FILE" "$OUTPUT_FILE" "$mod" &
    EXEC_PIDS+=($!)
  else
    echo "  [Executor] No contract for $mod — skipping"
  fi
done

# Wait for all parallel executor processes to complete
for pid in "${EXEC_PIDS[@]}"; do
  wait "$pid" || echo "  [Executor] Process $pid exited with non-zero status"
done

# ── Step 3: 개별 Evaluator 검증 ──
echo ""
echo "── Step 3: Individual review per module ──"
for mod in "${MODULE_LIST[@]}"; do
  mod=$(echo "$mod" | tr -d ' ')
  echo "  [Reviewer] Module: $mod"
  CONTRACT_FILE="$AGENT_DIR/contracts/${TIMESTAMP}_team_${mod}_contract.json"
  OUTPUT_FILE="$AGENT_DIR/outputs/${TIMESTAMP}_team_${mod}_output.json"
  VERDICT_FILE="$AGENT_DIR/verdicts/${TIMESTAMP}_team_${mod}_verdict.json"

  if [ -f "$OUTPUT_FILE" ]; then
    REVIEW_INPUT="$AGENT_DIR/requests/${TIMESTAMP}_team_${mod}_review.txt"
    cat > "$REVIEW_INPUT" <<EOF
PLAN:
$(cat "$CONTRACT_FILE" 2>/dev/null || echo "{}")

EXECUTION OUTPUT:
$(cat "$OUTPUT_FILE")

Module: $mod
Review adversarially. Output JSON verdict.
EOF
    bash scripts/agents/call_agent.sh reviewer "$REVIEW_INPUT" "$VERDICT_FILE"
  fi
done

# ── Step 4: 통합 결과 ──
echo ""
echo "── Step 4: Integration summary ──"
SUMMARY_FILE="$AGENT_DIR/results/${TIMESTAMP}_team_summary.json"

export TEAM_TASK="$TASK" TEAM_MODULES="$MODULES" TEAM_TIMESTAMP="$TIMESTAMP" TEAM_AGENT_DIR="$AGENT_DIR"
python3 -c "
import json, glob, os

agent_dir = os.environ['TEAM_AGENT_DIR']
timestamp = os.environ['TEAM_TIMESTAMP']

verdicts = {}
for f in glob.glob(os.path.join(agent_dir, f'verdicts/{timestamp}_team_*_verdict.json')):
    mod = os.path.basename(f).split('_team_')[1].split('_verdict')[0]
    try:
        verdicts[mod] = json.load(open(f))
    except:
        verdicts[mod] = {'error': 'parse_failed'}

summary = {
    'timestamp': os.environ['TEAM_TIMESTAMP'],
    'task': os.environ['TEAM_TASK'],
    'modules': os.environ['TEAM_MODULES'].split(','),
    'verdicts': verdicts,
    'overall': 'pass' if all(
        v.get('verdict') == 'approved' or v.get('overall_status') == 'pass'
        for v in verdicts.values()
    ) else 'needs_revision'
}

print(json.dumps(summary, ensure_ascii=False, indent=2))
" | tee "$SUMMARY_FILE"
