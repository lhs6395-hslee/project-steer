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
        # --bare: skips hooks, MCP, CLAUDE.md (full isolation)
        # --tools "": disables ALL tools → pure JSON text output
        # --json-schema: forces structured_output in response (v2.1)
        # --model sonnet: fast, reliable for structured output
        # 공식 근거: code.claude.com/docs/en/cli-reference.md
        echo "$INPUT" | timeout 180 claude --print \
          --bare \
          --model sonnet \
          --system-prompt "$SYSTEM_PROMPT" \
          --output-format json \
          --json-schema "$PLANNER_SCHEMA" \
          --max-turns 3 \
          --tools "" \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
      reviewer)
        # --json-schema: forces verdict schema validation (v2.1)
        # 공식 근거: code.claude.com/docs/en/agent-sdk/structured-outputs.md
        echo "$INPUT" | timeout 180 claude --print \
          --bare \
          --model sonnet \
          --system-prompt "$SYSTEM_PROMPT" \
          --output-format json \
          --json-schema "$REVIEWER_SCHEMA" \
          --max-turns 3 \
          --tools "" \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
      executor)
        # --bare: skips hooks + CLAUDE.md (prevents recursive pipeline)
        # --mcp-config: explicitly load needed MCP servers
        # --permission-mode bypassPermissions: auto-approve all tools including MCP
        # --json-schema: forces constraint_compliance output (v2.1)
        # --model sonnet: faster execution for multi-turn tool use
        # 공식 근거: code.claude.com/docs/en/cli-reference.md
        local MCP_CONFIG=".mcp.json"
        echo "$INPUT" | timeout 600 claude --print \
          --bare \
          --model sonnet \
          --system-prompt "$SYSTEM_PROMPT" \
          --output-format json \
          --json-schema "$EXECUTOR_SCHEMA" \
          --max-turns 20 \
          --permission-mode bypassPermissions \
          --mcp-config "$MCP_CONFIG" \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
      *)
        # Default: bare mode, limited turns, no schema
        echo "$INPUT" | timeout 180 claude --print \
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
    echo "$INPUT" | timeout 120 gemini \
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
