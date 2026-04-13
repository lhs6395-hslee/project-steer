#!/bin/bash
# Confidence_Trigger — 작업 위험도/복잡도 평가
# 4차원 점수 산출: ambiguity, domain_complexity, stakes, context_dependency
# 종합 점수에 따라 파이프라인 모드 결정
#
# Usage: bash scripts/agents/confidence_trigger.sh "<task_description>" "<module>"
# Output: JSON { score, mode, max_retries, ultraplan, agent_team }

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in confidence_trigger.sh (line $LINENO)" >&2; exit 2' ERR

TASK="${1:?Usage: confidence_trigger.sh <task> <module>}"
MODULE="${2:-unknown}"

export TASK MODULE

python3 -c "
import json, re, sys, os

task = os.environ['TASK']
module = os.environ['MODULE']

# ── 차원별 점수 산출 ──

# 1. Ambiguity: 요청이 모호한가
ambiguity = 0.5
if len(task) < 20: ambiguity = 0.8  # 짧은 요청 = 모호
elif len(task) > 200: ambiguity = 0.2  # 상세한 요청
if '?' in task: ambiguity = min(ambiguity + 0.1, 1.0)

# 2. Domain complexity: 모듈 복잡도
complexity_map = {
    'pptx': 0.4, 'docx': 0.3, 'wbs': 0.5, 'trello': 0.3,
    'dooray': 0.4, 'gdrive': 0.2, 'datadog': 0.6, 'unknown': 0.5
}
domain = complexity_map.get(module, 0.5)

# 3. Stakes: 위험도
stakes = 0.3
security_keywords = ['인증', 'auth', '권한', 'permission', '암호', 'encrypt', 'key', 'secret', 'delete', '삭제']
has_security_keyword = any(k in task.lower() for k in security_keywords)
if has_security_keyword:
    stakes = 0.8  # 보안 관련 = 고위험
production_keywords = ['운영', 'production', 'prd', 'cutover', '컷오버', 'deploy']
if any(k in task.lower() for k in production_keywords):
    stakes = max(stakes, 0.7)

# 4. Context dependency: 외부 데이터 의존
context = 0.3
data_keywords = ['WBS', 'Trello', 'Dooray', 'Drive', 'Datadog', 'API', '데이터', 'data']
if any(k in task for k in data_keywords):
    context = 0.6

# ── 종합 점수 (가중 평균) ──
score = 1.0 - (ambiguity * 0.25 + domain * 0.25 + stakes * 0.3 + context * 0.2)
score = round(max(0.0, min(1.0, score)), 2)

# ── 보안 키워드 클램핑: 반드시 multi-agent 파이프라인 강제 (Req 9.7) ──
if has_security_keyword:
    score = min(score, 0.69)

# ── 파이프라인 모드 결정 ──
if score >= 0.85:
    mode, max_retries, ultraplan, agent_team = 'single', 0, False, False
elif score >= 0.70:
    mode, max_retries, ultraplan, agent_team = 'multi_reduced', 3, False, False
elif score >= 0.50:
    mode, max_retries, ultraplan, agent_team = 'multi_full', 5, False, False
else:
    mode, max_retries, ultraplan, agent_team = 'multi_ultraplan', 5, True, False

result = {
    'score': score,
    'dimensions': {
        'ambiguity': round(ambiguity, 2),
        'domain_complexity': round(domain, 2),
        'stakes': round(stakes, 2),
        'context_dependency': round(context, 2)
    },
    'mode': mode,
    'max_retries': max_retries,
    'ultraplan': ultraplan,
    'agent_team': agent_team,
    'task': task[:100],
    'module': module
}

print(json.dumps(result, ensure_ascii=False, indent=2))
"
