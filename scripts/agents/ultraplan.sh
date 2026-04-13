#!/bin/bash
# UltraPlan — 계층적 태스크 분해
# Confidence_Trigger 점수 0.50 미만에서 활성화
# 최상위 목표를 하위 목표로 분해, 각각 독립 Sprint_Contract로 변환
#
# Usage: bash scripts/agents/ultraplan.sh "<task>" "<module>"

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in ultraplan.sh (line $LINENO)" >&2; exit 2' ERR

source "$(dirname "$0")/ide_adapter.sh"
ensure_agent_dirs

TASK="${1:?Usage: ultraplan.sh <task> <module>}"
MODULE="${2:?Usage: ultraplan.sh <task> <module>}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
PLAN_FILE="$AGENT_DIR/plans/${TIMESTAMP}_ultraplan.json"

echo "=== UltraPlan — Hierarchical Task Decomposition ==="
echo "Task: $TASK"
echo "Module: $MODULE"

# UltraPlan은 LLM 호출이 필요 — call_agent.sh를 통해 Planner를 UltraPlan 모드로 호출
ULTRAPLAN_INPUT="$AGENT_DIR/requests/${TIMESTAMP}_ultraplan_input.txt"

cat > "$ULTRAPLAN_INPUT" <<EOF
당신은 UltraPlan 모드의 Planner입니다.
아래 작업을 계층적 태스크 트리로 분해하세요.

작업: $TASK
모듈: $MODULE

규칙:
- 최대 3단계 깊이까지 분해
- 각 리프 태스크는 단일 Sprint_Contract로 실행 가능한 크기
- 독립적인 태스크는 병렬 실행 가능하도록 표시
- 의존적인 태스크는 순차 실행으로 표시

출력 형식 (JSON):
{
  "root_goal": "최상위 목표",
  "sub_goals": [
    {
      "id": "SG1",
      "goal": "하위 목표",
      "dependencies": [],
      "parallel": true,
      "sub_tasks": [
        {
          "id": "ST1.1",
          "action": "구체적 작업",
          "module": "$MODULE",
          "estimated_complexity": "low|medium|high"
        }
      ]
    }
  ],
  "dependency_graph": {
    "SG1": [],
    "SG2": ["SG1"]
  },
  "execution_order": [["SG1", "SG3"], ["SG2"]]
}
EOF

bash scripts/agents/call_agent.sh planner "$ULTRAPLAN_INPUT" "$PLAN_FILE" "$MODULE"

echo "UltraPlan saved: $PLAN_FILE"
