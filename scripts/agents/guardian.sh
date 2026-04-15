#!/bin/bash
# Guardian — Pattern_Matcher 기반 위험 명령/MCP tool 차단
# Claude API 호출 없이 정규식만으로 즉각 판정 (200ms 이내)
#
# Exit codes:
#   0 = 허용 (경고 포함 — 경고 시 stderr에 메시지 출력)
#   2 = 차단
#
# Usage: echo '{"tool_input":{"command":"rm -rf /"}}' | bash scripts/agents/guardian.sh
#        echo '{"tool_input":{"path":"/etc/passwd"}}' | bash scripts/agents/guardian.sh
#
# Indirect Prompt Injection 방어 (ClawGuard/CoopGuard 패턴)
# 근거: arXiv 2024 — "user-confirmed rule set at every tool-call boundary"
#       "attackers embed malicious instructions within tool-returned content"

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in guardian.sh (line $LINENO)" >&2; exit 2' ERR
INPUT=$(cat)

# Extract both command and tool-specific fields
CMD=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ti = data.get('tool_input', {})
# Bash command
cmd = ti.get('command', '')
# MCP/file tool fields — check path, file_path, content for injection
path = ti.get('path', ti.get('file_path', ''))
tool_name = data.get('tool_name', '')
# Combine for pattern matching
print(cmd or path or '')
" 2>/dev/null || echo "")

# ── MCP Tool-level checks (Indirect Prompt Injection 방어) ──
# 근거: arXiv 2024 ClawGuard — "rule set at every tool-call boundary"
MCP_TOOL=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('tool_name', data.get('tool_use_name', '')))
" 2>/dev/null || echo "")

# Block MCP tools attempting to access sensitive system paths
if [ -n "$MCP_TOOL" ] && echo "$MCP_TOOL" | grep -qiE "^mcp__"; then
  TOOL_INPUT_STR=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(json.dumps(data.get('tool_input', {})))
" 2>/dev/null || echo "")
  # Check for path traversal or sensitive system paths in MCP tool inputs
  if echo "$TOOL_INPUT_STR" | grep -qiE '(\.\./){2,}|/etc/passwd|/etc/shadow|/root/\.ssh|~/.claude/settings'; then
    echo "BLOCKED: MCP tool '$MCP_TOOL' attempting to access sensitive path" >&2
    echo "Input: $TOOL_INPUT_STR" >&2
    exit 2
  fi
fi

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

# ── 경고 (exit 0 + stderr 경고 메시지, 비차단) ──
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
    exit 0  # 경고만 출력, 차단하지 않음 (스펙 AC3: exit 0 + 경고 메시지)
  fi
done

# ── 허용 ──
exit 0
