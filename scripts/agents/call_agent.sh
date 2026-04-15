#!/bin/bash
# Universal sub-agent caller — v2.1: --json-schema structured output
#
# Usage:
#   bash scripts/agents/call_agent.sh <role> <input_file> <output_file> [module]
#
# v2.1 Changes (공식 문서 근거):
#   - Planner: --json-schema schemas/sprint_contract.schema.json
#     → structured_output 필드에 검증된 Sprint_Contract JSON 반환
#   - Reviewer: --json-schema schemas/verdict.schema.json
#     → structured_output 필드에 검증된 Verdict JSON 반환
#   - Executor: --json-schema schemas/executor_output.schema.json
#     → constraint_compliance, retry_fixes 등 필수 필드 강제
#
# Official docs:
#   - --json-schema flag: code.claude.com/docs/en/cli-reference.md
#   - Structured outputs: code.claude.com/docs/en/agent-sdk/structured-outputs.md
#   - JSON response format: code.claude.com/docs/en/headless.md
#   - Subagent definitions: code.claude.com/docs/en/agent-sdk/subagents.md
#
# Key design decisions:
#   - Planner/Reviewer: --bare --tools "" disables ALL tools + hooks, forcing pure JSON output
#   - Executor: --bare --mcp-config (tools + MCP, no hooks/CLAUDE.md)
#   - --output-format json + --json-schema → {"type":"result","structured_output":{...}}
#   - structured_output field contains schema-validated JSON (no markdown wrapping)

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in call_agent.sh (line $LINENO)" >&2; exit 2' ERR

ROLE="${1:?Usage: call_agent.sh <role> <input_file> <output_file> [module]}"
INPUT_FILE="${2:?}"
OUTPUT_FILE="${3:?}"
MODULE="${4:-}"

SKILL_FILE="skills/${ROLE}/SKILL.md"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ ! -f "$SKILL_FILE" ]; then
  echo "ERROR: Skill file not found: $SKILL_FILE" >&2
  exit 1
fi

# Build system prompt
SYSTEM_PROMPT="$(cat "$SKILL_FILE")"

if [ -n "$MODULE" ] && [ -f "modules/${MODULE}/SKILL.md" ] && [[ "$ROLE" =~ ^(planner|executor)$ ]]; then
  SYSTEM_PROMPT="${SYSTEM_PROMPT}

---
MODULE SKILL:
$(cat "modules/${MODULE}/SKILL.md")"
fi

if [ "$ROLE" = "reviewer" ] && [ -f "skills/orchestrator/references/module-checklists.md" ]; then
  SYSTEM_PROMPT="${SYSTEM_PROMPT}

---
MODULE CHECKLISTS:
$(cat "skills/orchestrator/references/module-checklists.md")"
fi

INPUT="$(cat "$INPUT_FILE")"

# ─── Load JSON schemas for --json-schema flag ───
# 공식 근거: code.claude.com/docs/en/cli-reference.md — --json-schema flag
# 공식 근거: code.claude.com/docs/en/agent-sdk/structured-outputs.md
PLANNER_SCHEMA="$(cat "$PROJECT_ROOT/schemas/sprint_contract.schema.json")"
REVIEWER_SCHEMA="$(cat "$PROJECT_ROOT/schemas/verdict.schema.json")"
EXECUTOR_SCHEMA="$(cat "$PROJECT_ROOT/schemas/executor_output.schema.json")"

# ─── Timeout command detection (macOS compatibility) ───
run_with_timeout() {
  local timeout_seconds="$1"
  shift
  if command -v timeout &>/dev/null; then
    timeout "$timeout_seconds" "$@"
  elif command -v gtimeout &>/dev/null; then
    gtimeout "$timeout_seconds" "$@"
  else
    # Fallback: perl-based timeout for macOS
    perl -e 'alarm shift; exec @ARGV' "$timeout_seconds" "$@"
  fi
}

# ─── Platform Detection + Retry Logic (max 2 retries) ───
MAX_RETRIES=2
ATTEMPT=0

# Extract structured_output from claude --print JSON response
# 공식 근거: code.claude.com/docs/en/headless.md
# With --json-schema: response has "structured_output" field (schema-validated JSON)
# Without --json-schema: response has "result" field (text, needs markdown stripping)
extract_structured_output() {
  local TMP_OUTPUT="$1"
  local DEST="$2"
  python3 "$SCRIPT_DIR/../utils/extract_result.py" "$TMP_OUTPUT" "$DEST" 2>&1
}

call_agent_once() {
  # ── 1. Claude Code (preferred) ──
  if command -v claude &>/dev/null; then
    local TMP_OUTPUT
    TMP_OUTPUT=$(mktemp)

    case "$ROLE" in
      planner)
        # --bare: skips hooks, MCP, CLAUDE.md (full isolation, faster start)
        #   공식 근거: code.claude.com/docs/en/cli-reference.md#--bare
        # --tools "": disables ALL tools → pure JSON text output
        # --json-schema: structured_output 필드에 schema-validated JSON 반환
        #   공식 근거: code.claude.com/docs/en/agent-sdk/structured-outputs
        # --model sonnet: Sprint_Contract DAG + 위험도/제약조건 추출 → 복잡한 추론 필요
        # --exclude-dynamic-system-prompt-sections: 프롬프트 캐시 재사용 개선 (속도↑)
        #   공식 근거: code.claude.com/docs/en/cli-reference.md (신규 플래그)
        echo "$INPUT" | run_with_timeout 180 claude --print \
          --bare \
          --model sonnet \
          --system-prompt "$SYSTEM_PROMPT" \
          --output-format json \
          --json-schema "$PLANNER_SCHEMA" \
          --max-turns 3 \
          --tools "" \
          --exclude-dynamic-system-prompt-sections \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
      reviewer)
        # --model: REVIEWER_MODEL env (default sonnet, opus for critical tasks)
        #   adversarial review 품질이 파이프라인 신뢰도를 결정 — 품질 타협 금지
        #   속도는 parallel_reviewer.py의 per-step 병렬화로 보완
        # --effort: REVIEWER_EFFORT env (default high) — 품질 중시
        #   공식 근거: code.claude.com/docs/en/cli-reference.md#--effort
        #   options: low, medium, high, max (max는 Opus 4.6 전용)
        # --exclude-dynamic-system-prompt-sections: 병렬 Reviewer 캐시 재사용 (속도↑)
        # 공식 근거: code.claude.com/docs/en/agent-sdk/structured-outputs
        local REVIEW_MODEL="${REVIEWER_MODEL:-sonnet}"
        local REVIEW_EFFORT="${REVIEWER_EFFORT:-high}"
        echo "$INPUT" | run_with_timeout 360 claude --print \
          --bare \
          --model "$REVIEW_MODEL" \
          --effort "$REVIEW_EFFORT" \
          --system-prompt "$SYSTEM_PROMPT" \
          --output-format json \
          --json-schema "$REVIEWER_SCHEMA" \
          --max-turns 3 \
          --tools "" \
          --exclude-dynamic-system-prompt-sections \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
      executor)
        # --bare: skips hooks + CLAUDE.md (prevents recursive pipeline trigger)
        # --mcp-config: explicitly load needed MCP servers
        # --permission-mode bypassPermissions: auto-approve all tools including MCP
        #   공식 근거: code.claude.com/docs/en/permission-modes
        # --json-schema: constraint_compliance 필드 강제
        # --model: EXECUTOR_MODEL env (default sonnet, opus for complex tasks)
        # --effort: EXECUTOR_EFFORT env (default high)
        # --max-turns: adaptive via EXECUTOR_MAX_TURNS (complexity 기반: low=10, med=20, high=40)
        # --fallback-model: 모델 과부하 시 sonnet으로 fallback
        #   공식 근거: code.claude.com/docs/en/cli-reference.md (신규 플래그)
        local MCP_CONFIG=".mcp.json"
        local EXEC_MODEL="${EXECUTOR_MODEL:-sonnet}"
        local EXEC_TURNS="${EXECUTOR_MAX_TURNS:-20}"
        local EXEC_TIMEOUT="${EXECUTOR_TIMEOUT:-900}"
        local EXEC_EFFORT="${EXECUTOR_EFFORT:-high}"
        echo "$INPUT" | run_with_timeout "$EXEC_TIMEOUT" claude --print \
          --bare \
          --model "$EXEC_MODEL" \
          --effort "$EXEC_EFFORT" \
          --system-prompt "$SYSTEM_PROMPT" \
          --output-format json \
          --json-schema "$EXECUTOR_SCHEMA" \
          --max-turns "$EXEC_TURNS" \
          --permission-mode bypassPermissions \
          --mcp-config "$MCP_CONFIG" \
          --fallback-model sonnet \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
      *)
        # Default: bare mode, limited turns, no schema
        echo "$INPUT" | run_with_timeout 180 claude --print \
          --bare \
          --model sonnet \
          --system-prompt "$SYSTEM_PROMPT" \
          --output-format json \
          --max-turns 5 \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
    esac

    local CLI_STATUS=$?
    if [ "$CLI_STATUS" -ne 0 ]; then
      echo "ERROR: claude --print exited with status $CLI_STATUS" >&2
      cat "$TMP_OUTPUT" >&2 2>/dev/null || true
      rm -f "$TMP_OUTPUT"
      return 1
    fi

    # Extract structured_output or .result field from wrapper JSON
    extract_structured_output "$TMP_OUTPUT" "$OUTPUT_FILE"
    local EXTRACT_STATUS=$?
    rm -f "$TMP_OUTPUT"
    return $EXTRACT_STATUS
  fi

  # ── 2. Gemini CLI (Antigravity) ──
  if command -v gemini &>/dev/null; then
    echo "$INPUT" | run_with_timeout 120 gemini \
      --system-instruction "$SYSTEM_PROMPT" \
      --json > "$OUTPUT_FILE" 2>/dev/null
    return 0
  fi

  # ── 3. Fallback — output skill + input for manual processing ──
  echo "WARNING: No supported CLI found (claude, gemini). Writing guidance file." >&2
  {
    echo "=== SYSTEM PROMPT ==="
    echo "$SYSTEM_PROMPT"
    echo ""
    echo "=== INPUT ==="
    echo "$INPUT"
    echo ""
    echo "=== INSTRUCTION ==="
    echo "Process the INPUT according to the SYSTEM PROMPT and save output as JSON."
  } > "$OUTPUT_FILE"
  return 1
}

while [ "$ATTEMPT" -le "$MAX_RETRIES" ]; do
  if call_agent_once; then
    exit 0
  fi
  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -le "$MAX_RETRIES" ]; then
    echo "RETRY: Attempt $((ATTEMPT)) of $((MAX_RETRIES)) for $ROLE agent..." >&2
    sleep 2
  fi
done

echo "ERROR: Agent $ROLE failed after $((MAX_RETRIES + 1)) attempts" >&2
exit 2
