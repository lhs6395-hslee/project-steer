#!/bin/bash
# Guardian — Pattern_Matcher 기반 위험 명령 차단
# Claude API 호출 없이 정규식만으로 즉각 판정 (200ms 이내)
#
# Exit codes:
#   0 = 허용
#   1 = 경고 (비차단)
#   2 = 차단
#
# Usage: echo '{"tool_input":{"command":"rm -rf /"}}' | bash scripts/agents/guardian.sh

set -euo pipefail

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

if [ -z "$CMD" ]; then
  exit 0  # 명령이 아닌 경우 허용
fi

# ── 무조건 차단 (exit 2) ──
BLOCK_PATTERNS=(
  'DROP\s+DATABASE'
  'DROP\s+SCHEMA'
  'kubectl\s+delete\s+namespace\s+(kube-system|kube-public|default)'
  'rm\s+-rf\s+/'
  'rm\s+-rf\s+/usr'
  'rm\s+-rf\s+/etc'
  'rm\s+-rf\s+/var'
  'rm\s+-rf\s+/home'
  'rm\s+-rf\s+~'
  'git\s+push\s+--force.*\s+(main|master)'
  'git\s+push\s+-f.*\s+(main|master)'
  'mkfs\.'
  'dd\s+if=.*\s+of=/dev/'
  '>\s*/dev/sd'
  'chmod\s+-R\s+777\s+/'
)

for pattern in "${BLOCK_PATTERNS[@]}"; do
  if echo "$CMD" | grep -qiE "$pattern"; then
    echo "BLOCKED: Command matches dangerous pattern '$pattern'" >&2
    echo "Command: $CMD" >&2
    exit 2
  fi
done

# ── 경고 (exit 1, 비차단) ──
WARN_PATTERNS=(
  'DROP\s+TABLE'
  'TRUNCATE'
  'kubectl\s+delete'
  'docker\s+compose\s+down\s+-v'
  'docker\s+system\s+prune'
  'git\s+reset\s+--hard'
  'git\s+clean\s+-fd'
  'rm\s+-rf'
)

for pattern in "${WARN_PATTERNS[@]}"; do
  if echo "$CMD" | grep -qiE "$pattern"; then
    echo "WARNING: Command matches cautionary pattern '$pattern'" >&2
    echo "Command: $CMD" >&2
    exit 1
  fi
done

# ── 허용 ──
exit 0
