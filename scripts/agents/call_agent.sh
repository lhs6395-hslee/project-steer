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

# ── Resolve actual model IDs from ~/.claude/settings.json ──
# --bare 모드는 settings.json을 로드하지 않아 alias(opus/sonnet)가 resolve되지 않음
# settings.json의 ANTHROPIC_DEFAULT_*_MODEL을 읽어 실제 모델 ID로 직접 사용
# 공식 근거: code.claude.com/docs/en/model-config#environment-variables
_SETTINGS="$HOME/.claude/settings.json"
_RESOLVED_OPUS="opus"
_RESOLVED_SONNET="sonnet"
_RESOLVED_HAIKU="haiku"
if [ -f "$_SETTINGS" ]; then
  eval "$(python3 - "$_SETTINGS" << 'PYEOF'
import json, sys, os
with open(sys.argv[1]) as f:
    s = json.load(f)
env = s.get('env', {})
# Unset conflicting provider vars first (shell env may have stale values)
all_provider_keys = ('CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_BEDROCK',
                     'CLOUD_ML_REGION','ANTHROPIC_VERTEX_PROJECT_ID','AWS_REGION')
for k in all_provider_keys:
    print(f"unset {k}")
# Export provider env vars from settings.json
for k in all_provider_keys:
    v = env.get(k)
    if v:
        print(f"export {k}={v!r}")
# Resolve model aliases to actual IDs
opus   = env.get('ANTHROPIC_DEFAULT_OPUS_MODEL', 'opus')
sonnet = env.get('ANTHROPIC_DEFAULT_SONNET_MODEL', 'sonnet')
haiku  = env.get('ANTHROPIC_DEFAULT_HAIKU_MODEL', 'haiku')
print(f"_RESOLVED_OPUS={opus!r}")
print(f"_RESOLVED_SONNET={sonnet!r}")
print(f"_RESOLVED_HAIKU={haiku!r}")
PYEOF
  2>/dev/null)" 2>/dev/null || true
fi

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
# env -i로 완전히 깨끗한 환경 시작 후 필요한 변수만 전달
# 근거: `env VAR=` 는 unset이 아니라 빈 문자열 set — 충돌 방지 불충분
# env -i는 부모 shell의 모든 env를 차단하고 명시한 변수만 전달
# HOME, PATH, TMPDIR, USER는 claude CLI 동작에 필요하므로 명시 전달
_ENV_PREFIX="env -i \
  HOME=${HOME} \
  PATH=${PATH} \
  TMPDIR=${TMPDIR:-/tmp} \
  USER=${USER:-$(id -un)} \
  CLAUDE_CODE_USE_VERTEX=${CLAUDE_CODE_USE_VERTEX:-} \
  CLOUD_ML_REGION=${CLOUD_ML_REGION:-} \
  ANTHROPIC_VERTEX_PROJECT_ID=${ANTHROPIC_VERTEX_PROJECT_ID:-} \
  ANTHROPIC_DEFAULT_OPUS_MODEL=${_RESOLVED_OPUS} \
  ANTHROPIC_DEFAULT_SONNET_MODEL=${_RESOLVED_SONNET} \
  ANTHROPIC_DEFAULT_HAIKU_MODEL=${_RESOLVED_HAIKU}"

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
# 공식 근거: code.claude.com/docs/en/agent-sdk/structured-outputs
#   result message: { "type": "result", "subtype": "success", "structured_output": {...} }
#   failure case:   { "type": "result", "subtype": "error_max_structured_output_retries" }
# extract_result.py가 없으므로 인라인 Python으로 처리
extract_structured_output() {
  local TMP_OUTPUT="$1"
  local DEST="$2"
  python3 - "$TMP_OUTPUT" "$DEST" << 'PYEOF'
import json, sys, re

src, dst = sys.argv[1], sys.argv[2]
try:
    raw = open(src).read().strip()
except Exception as e:
    print(f"ERROR: cannot read {src}: {e}", file=sys.stderr); sys.exit(1)

# Try parsing as JSON (--output-format json response)
try:
    data = json.loads(raw)
    # 공식 포맷: {"type":"result","subtype":"success","structured_output":{...}}
    subtype = data.get("subtype", "")
    if subtype == "error_max_structured_output_retries":
        print("ERROR: structured output retries exhausted", file=sys.stderr)
        sys.exit(1)
    if "structured_output" in data and data["structured_output"] is not None:
        with open(dst, "w") as f:
            json.dump(data["structured_output"], f, ensure_ascii=False, indent=2)
        sys.exit(0)
    # Fallback: "result" field (no --json-schema)
    if "result" in data:
        result_text = data["result"]
        # Strip markdown code fences if present
        result_text = re.sub(r'^```(?:json)?\s*', '', result_text.strip(), flags=re.MULTILINE)
        result_text = re.sub(r'```\s*$', '', result_text.strip(), flags=re.MULTILINE)
        parsed = json.loads(result_text.strip())
        with open(dst, "w") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        sys.exit(0)
except json.JSONDecodeError:
    pass

# Last resort: raw text might be JSON directly
try:
    stripped = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE)
    parsed = json.loads(stripped.strip())
    with open(dst, "w") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    sys.exit(0)
except Exception as e:
    print(f"ERROR: cannot extract JSON from output: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

call_agent_once() {
  # ── 1. Claude Code (preferred) ──
  if command -v claude &>/dev/null; then
    local TMP_OUTPUT
    # system prompt를 파일로 저장 — 큰 문자열을 인수로 전달 시 pipe blocking 방지
    local TMP_PROMPT TMP_INPUT
    TMP_PROMPT=$(mktemp)
    TMP_INPUT=$(mktemp)
    printf '%s' "$SYSTEM_PROMPT" > "$TMP_PROMPT"
    printf '%s' "$INPUT" > "$TMP_INPUT"
    TMP_OUTPUT=$(mktemp)

    case "$ROLE" in
      planner)
        # --bare: full isolation, faster start (skips hooks/MCP/CLAUDE.md)
        #   공식 근거: code.claude.com/docs/en/cli-reference.md#--bare
        # --tools "": disable ALL tools — pure JSON planning only
        # --json-schema: structured_output validated against sprint_contract.schema.json
        #   공식 근거: code.claude.com/docs/en/agent-sdk/structured-outputs
        # --model/--effort/--max-turns: env override (default from frontmatter: sonnet/high/3)
        #   모델 우선순위: env CLAUDE_CODE_SUBAGENT_MODEL > per-invocation > frontmatter > session
        #   공식 근거: code.claude.com/docs/en/sub-agents#choose-a-model
        # --exclude-dynamic-system-prompt-sections: prompt cache reuse 개선 (속도↑)
        #   공식 근거: code.claude.com/docs/en/cli-reference.md
        # --model opus: Planner가 파이프라인 품질 병목
        #   근거: arXiv 2024 "weak planner degrades overall performance more than weak executor"
        #   Planner만 opus 사용 → DAG 설계/위험도/제약조건 추출 품질 극대화
        # ANTHROPIC_DEFAULT_OPUS_MODEL이 settings.json에 provider별로 핀닝되어 있으므로
        # alias "opus"를 그대로 사용 — 실제 모델 ID는 env var이 결정
        local PLAN_MODEL="${PLANNER_MODEL:-$_RESOLVED_OPUS}"
        # effort medium: --json-schema + opus 조합에서 thinking 모드 비활성화
        # high/max effort는 thinking을 활성화해 tool_use API 제약과 충돌
        local PLAN_EFFORT="${PLANNER_EFFORT:-medium}"
        run_with_timeout 180 $_ENV_PREFIX claude --print \
          --bare \
          --model "$PLAN_MODEL" \
          --effort "$PLAN_EFFORT" \
          --system-prompt-file "$TMP_PROMPT" \
          --output-format json \
          --json-schema "$PLANNER_SCHEMA" \
          --max-turns 3 \
          --tools "" \
          --exclude-dynamic-system-prompt-sections \
          < "$TMP_INPUT" \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
      reviewer)
        # --model/--effort: env override (default: sonnet/high — 품질 타협 금지)
        #   속도는 parallel_reviewer.py per-step 병렬화로 보완
        # --exclude-dynamic-system-prompt-sections: 병렬 Reviewer 캐시 재사용
        # --max-turns 3: verdict is single-turn JSON, 3 turns = schema retry budget
        #   공식 근거: code.claude.com/docs/en/agent-sdk/structured-outputs
        #              (error_max_structured_output_retries — agent retries internally)
        local REVIEW_MODEL="${REVIEWER_MODEL:-$_RESOLVED_SONNET}"
        local REVIEW_EFFORT="${REVIEWER_EFFORT:-medium}"
        run_with_timeout 360 $_ENV_PREFIX claude --print \
          --bare \
          --model "$REVIEW_MODEL" \
          --effort "$REVIEW_EFFORT" \
          --system-prompt-file "$TMP_PROMPT" \
          --output-format json \
          --json-schema "$REVIEWER_SCHEMA" \
          --max-turns 3 \
          --tools "" \
          --exclude-dynamic-system-prompt-sections \
          < "$TMP_INPUT" \
          > "$TMP_OUTPUT" 2>/dev/null
        ;;
      executor)
        # --bare: prevents recursive pipeline trigger (no CLAUDE.md/hooks)
        # --permission-mode bypassPermissions: auto-approve MCP tools
        #   공식 근거: code.claude.com/docs/en/permission-modes
        # --model/--effort: env override (default: sonnet/high)
        #   opus 사용 시: EXECUTOR_MODEL=opus (결과 품질 우선)
        # --max-turns: complexity 기반 adaptive (low=10, medium=20, high=40)
        #   frontmatter maxTurns=20 (medium default); env로 override 가능
        # --fallback-model: 모델 과부하 시 sonnet 자동 fallback
        #   공식 근거: code.claude.com/docs/en/cli-reference.md#--fallback-model
        # isolation:worktree → frontmatter에서 처리 (병렬 step 파일 충돌 방지)
        #   공식 근거: code.claude.com/docs/en/sub-agents#supported-frontmatter-fields
        # Use MCP_FILE from ide_adapter if available, fallback to .mcp.json (#27 audit fix)
        local MCP_CONFIG="${MCP_FILE:-.mcp.json}"
        local EXEC_MODEL="${EXECUTOR_MODEL:-$_RESOLVED_SONNET}"
        local EXEC_TURNS="${EXECUTOR_MAX_TURNS:-80}"
        local EXEC_TIMEOUT="${EXECUTOR_TIMEOUT:-900}"
        local EXEC_EFFORT="${EXECUTOR_EFFORT:-medium}"
        # --json-schema + MCP tool use 조합: structured output 생성 전 tool turns 필요
        # max-turns를 40으로 올려야 MCP 실행 후 structured output 반환 가능
        # 공식 근거: code.claude.com/docs/en/cli-reference.md#--max-turns
        run_with_timeout "$EXEC_TIMEOUT" $_ENV_PREFIX claude --print \
          --bare \
          --model "$EXEC_MODEL" \
          --effort "$EXEC_EFFORT" \
          --system-prompt-file "$TMP_PROMPT" \
          --output-format json \
          --json-schema "$EXECUTOR_SCHEMA" \
          --max-turns "$EXEC_TURNS" \
          --permission-mode bypassPermissions \
          --mcp-config "$MCP_CONFIG" \
          --fallback-model "$_RESOLVED_SONNET" \
          < "$TMP_INPUT" \
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
    rm -f "$TMP_OUTPUT" "$TMP_PROMPT" "$TMP_INPUT"
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
