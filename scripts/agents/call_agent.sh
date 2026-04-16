#!/bin/bash
# Universal sub-agent caller — v2.3: direct env array execution (fixes word-split)
#
# Usage:
#   bash scripts/agents/call_agent.sh <role> <input_file> <output_file> [module]
#
# v2.3 수정 사항:
#   1. _ENV_PREFIX 문자열 word-split 버그 수정
#      - 기존: _ENV_PREFIX="env -i ..." unquoted word-split으로 실행
#        → --json-schema "$(cat file)" 확장 시 JSON 개행이 추가 인수로 분리 → exit 1
#      - 수정: call_claude() 함수 내에서 env -i를 직접 실행 (word-split 없음)
#   2. --json-schema JSON 한 줄 압축 전달
#      - 멀티라인 JSON을 직접 인수로 전달 시 word-split 가능성 제거
#      - python3으로 JSON 재직렬화 → 한 줄 압축 후 인수로 전달
#   3. Executor --json-schema 제거
#      - structured output 모드가 MCP 도구 호출을 억제 → 빈 출력 원인
#      - SKILL.md 프롬프트 지시로만 출력 포맷 제어
#   4. 2>/dev/null → TMP_ERR 파일로 변경 (실패 원인 가시성 확보)
#
# Official docs:
#   - CLI reference: code.claude.com/docs/en/cli-reference.md
#   - Headless: code.claude.com/docs/en/headless.md
#   - Subagents: code.claude.com/docs/en/agent-sdk/subagents.md

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
# --bare 모드는 settings.json을 로드하지 않아 alias가 resolve되지 않음
# 공식 근거: code.claude.com/docs/en/model-config#environment-variables
_SETTINGS="$HOME/.claude/settings.json"
_RESOLVED_OPUS="opus"
_RESOLVED_SONNET="sonnet"
_RESOLVED_HAIKU="haiku"
_VERTEX=""
_BEDROCK=""
_CLOUD_ML_REGION=""
_VERTEX_PROJECT=""
_AWS_REGION=""

if [ -f "$_SETTINGS" ]; then
  eval "$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    s = json.load(f)
env = s.get('env', {})
for k, v in [
    ('_VERTEX',          env.get('CLAUDE_CODE_USE_VERTEX', '')),
    ('_BEDROCK',         env.get('CLAUDE_CODE_USE_BEDROCK', '')),
    ('_CLOUD_ML_REGION', env.get('CLOUD_ML_REGION', '')),
    ('_VERTEX_PROJECT',  env.get('ANTHROPIC_VERTEX_PROJECT_ID', '')),
    ('_AWS_REGION',      env.get('AWS_REGION', '')),
]:
    print(f'{k}={v!r}')
print(f'_RESOLVED_OPUS={env.get(\"ANTHROPIC_DEFAULT_OPUS_MODEL\",\"opus\")!r}')
print(f'_RESOLVED_SONNET={env.get(\"ANTHROPIC_DEFAULT_SONNET_MODEL\",\"sonnet\")!r}')
print(f'_RESOLVED_HAIKU={env.get(\"ANTHROPIC_DEFAULT_HAIKU_MODEL\",\"haiku\")!r}')
" "$_SETTINGS" 2>/dev/null)" 2>/dev/null || true
fi

# Build system prompt
# .claude/agents/ROLE.md = primary (single source of truth)
# skills/ROLE/SKILL.md = fallback (legacy, orchestrator 참조용만 유지)
AGENT_DEF=".claude/agents/${ROLE}.md"
if [ -f "$AGENT_DEF" ]; then
  # frontmatter(---...---) 제거 후 본문만 추출
  SYSTEM_PROMPT="$(python3 -c "
import sys
content = open('$AGENT_DEF').read()
# strip YAML frontmatter
if content.startswith('---'):
    end = content.find('---', 3)
    if end != -1:
        content = content[end+3:].lstrip()
print(content, end='')
")"
elif [ -f "$SKILL_FILE" ]; then
  echo "WARN: .claude/agents/${ROLE}.md not found, falling back to $SKILL_FILE" >&2
  SYSTEM_PROMPT="$(cat "$SKILL_FILE")"
else
  echo "ERROR: Neither .claude/agents/${ROLE}.md nor $SKILL_FILE found" >&2
  exit 1
fi

# MODULE SKILL: 전체 주입 대신 step에 해당하는 레이아웃 섹션만 추출
# INPUT_FILE에서 target layout(L0N) 파싱 → 해당 섹션만 주입 (context 절감)
if [ -n "$MODULE" ] && [ -f "modules/${MODULE}/SKILL.md" ] && [[ "$ROLE" =~ ^(planner|executor)$ ]]; then
  # step input에서 레이아웃 코드 추출 (L01~L36)
  LAYOUT_CODE="$(grep -oP 'L\d{2}' "$INPUT_FILE" 2>/dev/null | head -1)"
  MODULE_SKILL_CONTENT="$(cat "modules/${MODULE}/SKILL.md")"

  if [ -n "$LAYOUT_CODE" ]; then
    # 해당 레이아웃 섹션만 추출 (### L0N ~ 다음 ### 또는 EOF까지)
    LAYOUT_SECTION="$(python3 -c "
import sys, re
content = open('modules/${MODULE}/SKILL.md').read()
layout = '$LAYOUT_CODE'
# 레이아웃별 섹션 추출
pattern = rf'(?:^|\n)(#{1,4}[^\n]*{re.escape(layout)}[^\n]*\n.*?)(?=\n#{1,4} |\Z)'
m = re.search(pattern, content, re.DOTALL)
if m:
    print(m.group(1)[:3000])  # 최대 3KB
else:
    # 섹션 없으면 공통 규칙(생성 방식, 필수 규칙)만 추출 (최대 2KB)
    lines = content.split('\n')
    common = []
    in_common = False
    for l in lines:
        if any(k in l for k in ['생성 방식', '필수 규칙', 'MCP 도구', '아이콘 사용']):
            in_common = True
        if in_common:
            common.append(l)
        if len('\n'.join(common)) > 2000:
            break
    print('\n'.join(common))
" 2>/dev/null)"

    if [ -n "$LAYOUT_SECTION" ]; then
      SYSTEM_PROMPT="${SYSTEM_PROMPT}

---
MODULE SKILL (${MODULE} / ${LAYOUT_CODE}):
${LAYOUT_SECTION}"
    else
      # 레이아웃 섹션 없음 → 공통 규칙만 (생성 방식 + MCP 매핑 테이블, ~2KB)
      COMMON_SKILL="$(python3 -c "
content = open('modules/${MODULE}/SKILL.md').read()
# 생성 방식 섹션까지만
idx = content.find('### Workflow')
if idx > 0:
    print(content[:idx][:3000])
else:
    print(content[:3000])
" 2>/dev/null)"
      SYSTEM_PROMPT="${SYSTEM_PROMPT}

---
MODULE SKILL (${MODULE} / common):
${COMMON_SKILL}"
    fi
  else
    # 레이아웃 코드 없는 경우(planner, merge step 등) → 공통 규칙만
    COMMON_SKILL="$(python3 -c "
content = open('modules/${MODULE}/SKILL.md').read()
idx = content.find('### Workflow')
if idx > 0:
    print(content[:idx][:3000])
else:
    print(content[:3000])
" 2>/dev/null)"
    SYSTEM_PROMPT="${SYSTEM_PROMPT}

---
MODULE SKILL (${MODULE} / common):
${COMMON_SKILL}"
  fi
fi

if [ "$ROLE" = "reviewer" ] && [ -f "skills/orchestrator/references/module-checklists.md" ]; then
  SYSTEM_PROMPT="${SYSTEM_PROMPT}

---
MODULE CHECKLISTS:
$(cat "skills/orchestrator/references/module-checklists.md")"
fi

INPUT="$(cat "$INPUT_FILE")"

# ── compact_json: JSON 파일을 한 줄로 압축 ──
# --json-schema 인수에 멀티라인 JSON을 전달하면 word-split 발생 가능
# → 한 줄로 압축하면 공백 포함 단일 인수로 안전하게 전달됨
compact_json() {
  python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1]))))" "$1"
}

# ── _build_provider_env: settings.json 기준 provider 환경 배열 구성 ──
# Vertex가 활성이면 BEDROCK 변수를 완전히 배제, Bedrock이면 VERTEX 변수 배제
# Kiro/VS Code IDE가 반대 provider 변수를 shell에 주입해도 env -i로 완전 차단
# 공식 근거: Claude Code CLI --bare 모드는 settings.json env를 로드하지 않으므로
#   claude subprocess에 직접 환경 변수를 전달해야 함
#   code.claude.com/docs/en/cli-reference.md#--bare
_BASE_ENV=(
  HOME="$HOME"
  PATH="$PATH"
  TMPDIR="${TMPDIR:-/tmp}"
  USER="${USER:-$(id -un)}"
  ANTHROPIC_DEFAULT_OPUS_MODEL="$_RESOLVED_OPUS"
  ANTHROPIC_DEFAULT_SONNET_MODEL="$_RESOLVED_SONNET"
  ANTHROPIC_DEFAULT_HAIKU_MODEL="$_RESOLVED_HAIKU"
)

if [ -n "${_VERTEX:-}" ]; then
  # Vertex 모드: BEDROCK 관련 변수 완전 제외 (빈 문자열도 미전달)
  _PROVIDER_ENV=(
    CLAUDE_CODE_USE_VERTEX="$_VERTEX"
    CLOUD_ML_REGION="${_CLOUD_ML_REGION:-}"
    ANTHROPIC_VERTEX_PROJECT_ID="${_VERTEX_PROJECT:-}"
  )
elif [ -n "${_BEDROCK:-}" ]; then
  # Bedrock 모드: VERTEX 관련 변수 완전 제외
  _PROVIDER_ENV=(
    CLAUDE_CODE_USE_BEDROCK="$_BEDROCK"
    AWS_REGION="${_AWS_REGION:-}"
  )
else
  # 기본: settings.json에 provider 없으면 ANTHROPIC_API_KEY 사용 (Anthropic Direct)
  _PROVIDER_ENV=()
fi

# call_claude: env -i + 고정 provider 환경으로 실행 (word-split 없음)
call_claude() {
  env -i "${_BASE_ENV[@]}" "${_PROVIDER_ENV[@]}" claude "$@"
}

# ─── Platform Detection + Retry Logic (max 2 retries) ───
MAX_RETRIES=2
ATTEMPT=0

# Extract JSON from claude --print response
# structured_output 필드 우선 (--json-schema 사용 시), fallback .result JSON 파싱
extract_structured_output() {
  local TMP_OUTPUT="$1"
  local DEST="$2"
  local _EX_PY
  _EX_PY=$(mktemp /tmp/call_agent_extract_XXXXXX.py)
  cat > "$_EX_PY" << 'PYEOF'
import json, sys, re

src, dst = sys.argv[1], sys.argv[2]
try:
    raw = open(src).read().strip()
except Exception as e:
    print(f"ERROR: cannot read {src}: {e}", file=sys.stderr); sys.exit(1)

try:
    data = json.loads(raw)
    # structured_output 필드 우선 (--json-schema 사용 시)
    if "structured_output" in data and data["structured_output"] is not None:
        with open(dst, "w") as f:
            json.dump(data["structured_output"], f, ensure_ascii=False, indent=2)
        sys.exit(0)
    # .result 필드에서 JSON 파싱 (프롬프트 기반)
    if "result" in data:
        result_text = data["result"]
        result_text = re.sub(r'^```(?:json)?\s*', '', result_text.strip(), flags=re.MULTILINE)
        result_text = re.sub(r'```\s*$', '', result_text.strip(), flags=re.MULTILINE)
        parsed = json.loads(result_text.strip())
        with open(dst, "w") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        sys.exit(0)
except json.JSONDecodeError:
    pass

# Last resort: raw text가 JSON인 경우
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
  python3 "$_EX_PY" "$TMP_OUTPUT" "$DEST"
  local _STATUS=$?
  rm -f "$_EX_PY"
  return $_STATUS
}

call_agent_once() {
  # ── 1. Claude Code (preferred) ──
  if command -v claude &>/dev/null; then
    local TMP_PROMPT TMP_INPUT TMP_OUTPUT TMP_ERR
    TMP_PROMPT=$(mktemp)
    TMP_INPUT=$(mktemp)
    TMP_OUTPUT=$(mktemp)
    TMP_ERR=$(mktemp)
    printf '%s' "$SYSTEM_PROMPT" > "$TMP_PROMPT"
    printf '%s' "$INPUT" > "$TMP_INPUT"

    local CLAUDE_EXIT=0

    case "$ROLE" in
      planner)
        # --bare: hooks/MCP/CLAUDE.md 스킵 (공식: code.claude.com/docs/en/cli-reference.md#--bare)
        # --tools "": 모든 도구 비활성화 — 순수 JSON 계획만 생성
        # --json-schema: sprint_contract.schema.json으로 구조화 출력 강제
        #   JSON 한 줄 압축 전달 — word-split 방지
        local PLAN_MODEL="${PLANNER_MODEL:-$_RESOLVED_OPUS}"
        local PLAN_EFFORT="${PLANNER_EFFORT:-medium}"
        local PLAN_SCHEMA
        PLAN_SCHEMA="$(compact_json "$PROJECT_ROOT/schemas/sprint_contract.schema.json")"
        call_claude --print \
          --bare \
          --model "$PLAN_MODEL" \
          --effort "$PLAN_EFFORT" \
          --append-system-prompt-file "$TMP_PROMPT" \
          --output-format json \
          --json-schema "$PLAN_SCHEMA" \
          --max-turns 3 \
          --tools "" \
          < "$TMP_INPUT" \
          > "$TMP_OUTPUT" 2>"$TMP_ERR" || CLAUDE_EXIT=$?
        ;;
      reviewer)
        # Reviewer에게 Bash+Read 도구 허용 — python-pptx로 PPTX 직접 열어 좌표 기반 검증
        # --tools "": 도구 없이 텍스트만 보면 시각적 겹침/아이콘 위치 검증 불가
        # 공식 근거: code.claude.com/docs/en/cli-reference.md#--tools
        local REVIEW_MODEL="${REVIEWER_MODEL:-$_RESOLVED_SONNET}"
        local REVIEW_EFFORT="${REVIEWER_EFFORT:-medium}"
        local REVIEW_SCHEMA
        REVIEW_SCHEMA="$(compact_json "$PROJECT_ROOT/schemas/verdict.schema.json")"
        call_claude --print \
          --bare \
          --model "$REVIEW_MODEL" \
          --effort "$REVIEW_EFFORT" \
          --append-system-prompt-file "$TMP_PROMPT" \
          --output-format json \
          --json-schema "$REVIEW_SCHEMA" \
          --max-turns 10 \
          --permission-mode bypassPermissions \
          < "$TMP_INPUT" \
          > "$TMP_OUTPUT" 2>"$TMP_ERR" || CLAUDE_EXIT=$?
        ;;
      executor)
        # --json-schema 제거: structured output 모드가 MCP 도구 호출을 억제함
        # --permission-mode bypassPermissions: MCP 도구 자동 승인
        #   공식 근거: code.claude.com/docs/en/permission-modes
        # --fallback-model: haiku 사용 (동일 모델 지정 시 CLI 오류)
        #   공식 근거: code.claude.com/docs/en/cli-reference.md#--fallback-model
        # timeout 처리: call_claude는 shell 함수라 외부 timeout에 직접 전달 불가
        # → timeout이 있으면 env -i를 직접 구성해서 timeout에 전달
        local MCP_CONFIG="${MCP_FILE:-.mcp.json}"
        local EXEC_MODEL="${EXECUTOR_MODEL:-$_RESOLVED_SONNET}"
        local EXEC_TURNS="${EXECUTOR_MAX_TURNS:-80}"
        local EXEC_TIMEOUT="${EXECUTOR_TIMEOUT:-900}"
        local EXEC_EFFORT="${EXECUTOR_EFFORT:-medium}"
        local EXEC_FALLBACK="${EXECUTOR_FALLBACK_MODEL:-$_RESOLVED_HAIKU}"
        local _TIMEOUT_CMD=""
        if command -v timeout &>/dev/null; then
          _TIMEOUT_CMD="timeout $EXEC_TIMEOUT"
        elif command -v gtimeout &>/dev/null; then
          _TIMEOUT_CMD="gtimeout $EXEC_TIMEOUT"
        fi
        # shellcheck disable=SC2086
        $_TIMEOUT_CMD \
          env -i "${_BASE_ENV[@]}" "${_PROVIDER_ENV[@]}" \
          claude --print \
            --bare \
            --model "$EXEC_MODEL" \
            --effort "$EXEC_EFFORT" \
            --append-system-prompt-file "$TMP_PROMPT" \
            --output-format json \
            --max-turns "$EXEC_TURNS" \
            --permission-mode bypassPermissions \
            --mcp-config "$MCP_CONFIG" \
            --fallback-model "$EXEC_FALLBACK" \
            < "$TMP_INPUT" \
            > "$TMP_OUTPUT" 2>"$TMP_ERR" || CLAUDE_EXIT=$?
        ;;
      *)
        call_claude --print \
          --bare \
          --model "$_RESOLVED_SONNET" \
          --append-system-prompt-file "$TMP_PROMPT" \
          --output-format json \
          --max-turns 5 \
          --permission-mode bypassPermissions \
          < "$TMP_INPUT" \
          > "$TMP_OUTPUT" 2>"$TMP_ERR" || CLAUDE_EXIT=$?
        ;;
    esac

    if [ "$CLAUDE_EXIT" -ne 0 ]; then
      echo "ERROR: claude --print exited with status $CLAUDE_EXIT (role=$ROLE)" >&2
      if [ -s "$TMP_ERR" ]; then
        echo "--- stderr ---" >&2
        cat "$TMP_ERR" >&2
        echo "--- end stderr ---" >&2
      fi
      if [ -s "$TMP_OUTPUT" ]; then
        echo "--- stdout (first 500 bytes) ---" >&2
        head -c 500 "$TMP_OUTPUT" >&2
        echo "" >&2
      fi
      rm -f "$TMP_OUTPUT" "$TMP_PROMPT" "$TMP_INPUT" "$TMP_ERR"
      return 1
    fi

    extract_structured_output "$TMP_OUTPUT" "$OUTPUT_FILE"
    local EXTRACT_STATUS=$?
    rm -f "$TMP_OUTPUT" "$TMP_PROMPT" "$TMP_INPUT" "$TMP_ERR"
    return $EXTRACT_STATUS
  fi

  # ── 2. Gemini CLI (Antigravity) ──
  if command -v gemini &>/dev/null; then
    echo "$INPUT" | gemini \
      --system-instruction "$SYSTEM_PROMPT" \
      --json > "$OUTPUT_FILE" 2>/dev/null
    return 0
  fi

  # ── 3. Fallback ──
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
