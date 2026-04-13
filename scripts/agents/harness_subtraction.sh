#!/bin/bash
# Harness_Subtraction — 하네스 최적화 분석
# 각 에이전트 컴포넌트의 기여도를 측정하고 불필요한 스캐폴딩 제거 제안
#
# Usage: bash scripts/agents/harness_subtraction.sh

set -euo pipefail

source "$(dirname "$0")/ide_adapter.sh"
ensure_agent_dirs

METRICS_DIR="$AGENT_DIR/metrics"
REPORTS_DIR="$AGENT_DIR/reports"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
REPORT_FILE="$REPORTS_DIR/${TIMESTAMP}_subtraction_report.json"

echo "=== Harness Subtraction — Optimization Analysis ==="

# ── 메트릭 수집 ──
# Evaluator fail 발견 횟수
EVAL_FAILS=$(find "$AGENT_DIR/verdicts" -name "*.json" 2>/dev/null | xargs grep -l '"overall_status":\s*"fail"' 2>/dev/null | wc -l | tr -d ' ')

# Guardian 차단 횟수 (로그 기반)
GUARDIAN_BLOCKS=$(find "$AGENT_DIR" -name "*guardian*" 2>/dev/null | wc -l | tr -d ' ')

# Planner 수정 횟수
PLANNER_REVISIONS=$(find "$AGENT_DIR/contracts" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')

# 전체 파이프라인 실행 횟수
TOTAL_RUNS=$(find "$AGENT_DIR/results" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')

# ── 기여도 분석 ──
python3 -c "
import json
from datetime import datetime

metrics = {
    'timestamp': '$TIMESTAMP',
    'period_days': 30,
    'components': {
        'evaluator': {
            'fail_detections': $EVAL_FAILS,
            'contribution': 'active' if $EVAL_FAILS > 0 else 'inactive',
            'recommendation': 'keep' if $EVAL_FAILS > 0 else 'review_for_removal'
        },
        'guardian': {
            'blocks': $GUARDIAN_BLOCKS,
            'contribution': 'active' if $GUARDIAN_BLOCKS > 0 else 'inactive',
            'recommendation': 'keep'  # Guardian은 항상 유지 (안전성)
        },
        'planner': {
            'contracts_generated': $PLANNER_REVISIONS,
            'contribution': 'active' if $PLANNER_REVISIONS > 0 else 'inactive',
            'recommendation': 'keep' if $PLANNER_REVISIONS > 0 else 'review_for_removal'
        }
    },
    'total_pipeline_runs': $TOTAL_RUNS,
    'optimization_suggestions': []
}

# 제안 생성
for name, comp in metrics['components'].items():
    if comp['recommendation'] == 'review_for_removal':
        metrics['optimization_suggestions'].append(
            f'{name}: 30일간 기여도 0. 비활성화 검토 권장.'
        )

if not metrics['optimization_suggestions']:
    metrics['optimization_suggestions'].append('모든 컴포넌트가 활성 상태. 최적화 불필요.')

print(json.dumps(metrics, ensure_ascii=False, indent=2))
" | tee "$REPORT_FILE"

echo ""
echo "Report saved: $REPORT_FILE"
