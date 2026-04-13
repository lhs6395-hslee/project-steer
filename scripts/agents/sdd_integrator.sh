#!/bin/bash
# SDD Integrator — Spec-Driven Development 통합
# requirements.md에서 인수 조건을 자동 추출하여 Sprint_Contract/Verdict에 반영
#
# Usage: bash scripts/agents/sdd_integrator.sh <module>

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in sdd_integrator.sh (line $LINENO)" >&2; exit 2' ERR

source "$(dirname "$0")/ide_adapter.sh"
ensure_agent_dirs

MODULE="${1:?Usage: sdd_integrator.sh <module>}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

echo "=== SDD Integrator — Extracting acceptance criteria ==="
echo "Module: $MODULE"

python3 -c "
import json, re

# PROJECT.md에서 모듈별 인수 조건 추출
with open('PROJECT.md') as f:
    content = f.read()

# 모듈 섹션 찾기
module_map = {
    'pptx': 'M1: PPTX', 'docx': 'M2: DOCX', 'wbs': 'M3: WBS',
    'trello': 'M4: Trello', 'dooray': 'M5: Dooray',
    'gdrive': 'M6: Google Drive', 'datadog': 'M7: Datadog'
}

section_header = module_map.get('$MODULE', '')
if not section_header:
    print(json.dumps({'error': 'Module not found in PROJECT.md'}))
    exit(1)

# 섹션 내용 추출
pattern = rf'### {re.escape(section_header)}.*?\n(.*?)(?=\n### |\n## |\Z)'
match = re.search(pattern, content, re.DOTALL)

if not match:
    print(json.dumps({'error': f'Section {section_header} not found'}))
    exit(1)

section_text = match.group(1)

# 불릿 항목을 인수 조건으로 변환
criteria = []
for i, line in enumerate(section_text.split('\n')):
    line = line.strip()
    if line.startswith('- '):
        criteria.append({
            'id': f'AC-{\"$MODULE\"}-{i+1}',
            'description': line[2:],
            'verification_method': 'manual_review',
            'source': 'PROJECT.md'
        })

result = {
    'module': '$MODULE',
    'extracted_at': '$TIMESTAMP',
    'criteria_count': len(criteria),
    'acceptance_criteria': criteria
}

print(json.dumps(result, ensure_ascii=False, indent=2))
"
