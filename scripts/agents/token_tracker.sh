#!/bin/bash
# Token Tracker — 비용 및 토큰 관리 (요구사항 14)
# 파이프라인 실행 후 토큰 사용량 집계
#
# Usage: bash scripts/agents/token_tracker.sh [pipeline_run_dir]

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in token_tracker.sh (line $LINENO)" >&2; exit 2' ERR

source "$(dirname "$0")/ide_adapter.sh"

RUN_DIR="${1:-$AGENT_DIR}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

echo "=== Token Usage Report ==="

python3 -c "
import json, os, glob, sys

run_dir = '$RUN_DIR'
total_input = 0
total_output = 0

# Handoff_File에서 token_usage 수집
for pattern in ['requests/*.json', 'contracts/*.json', 'outputs/*.json', 'verdicts/*.json']:
    for f in glob.glob(os.path.join(run_dir, pattern)):
        try:
            data = json.load(open(f))
            usage = data.get('token_usage', {})
            total_input += usage.get('input_tokens', 0)
            total_output += usage.get('output_tokens', 0)
        except:
            pass

# 비용 추정 (Claude Sonnet 기준)
input_cost = total_input * 3.0 / 1_000_000   # \$3/1M input tokens
output_cost = total_output * 15.0 / 1_000_000  # \$15/1M output tokens
total_cost = input_cost + output_cost

# 예산 확인 — config/token_budget.json 또는 run_dir 내 config/
budget = None
for budget_path in ['config/token_budget.json', os.path.join(run_dir, 'config', 'token_budget.json')]:
    if os.path.exists(budget_path):
        budget = json.load(open(budget_path))
        break

report = {
    'timestamp': '$TIMESTAMP',
    'total_input_tokens': total_input,
    'total_output_tokens': total_output,
    'total_tokens': total_input + total_output,
    'estimated_cost_usd': round(total_cost, 4),
    'breakdown': {
        'input_cost_usd': round(input_cost, 4),
        'output_cost_usd': round(output_cost, 4)
    }
}

exit_code = 0
if budget:
    max_tokens = budget.get('max_tokens', 0)
    total = total_input + total_output
    usage_pct = total / max_tokens * 100 if max_tokens > 0 else 0
    exceeded = usage_pct >= 100
    warning = usage_pct >= 80
    report['budget'] = {
        'max_tokens': max_tokens,
        'usage_percent': round(usage_pct, 1),
        'warning': warning,
        'exceeded': exceeded
    }
    if exceeded:
        print('TOKEN BUDGET EXCEEDED — pipeline should stop after current agent', file=sys.stderr)
        exit_code = 2
    elif warning:
        print(f'TOKEN BUDGET WARNING — {usage_pct:.1f}% of budget used', file=sys.stderr)

print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(exit_code)
"
