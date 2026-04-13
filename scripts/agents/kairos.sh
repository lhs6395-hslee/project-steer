#!/bin/bash
# KAIROS_Monitor — 경량 사전 감시 (lint-level)
# 파일 변경 시 빠른 피드백. Evaluator의 전체 검증과 범위 분리.
#
# Usage:
#   bash scripts/agents/kairos.sh <changed_file>
#   bash scripts/agents/kairos.sh --watch  (데몬 모드, 향후)

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in kairos.sh (line $LINENO)" >&2; exit 2' ERR

source "$(dirname "$0")/ide_adapter.sh"
ensure_agent_dirs

FILE="${1:?Usage: kairos.sh <file_path>}"

if [ "$FILE" = "--watch" ]; then
  echo "KAIROS daemon mode not yet implemented. Use file event hooks instead."
  exit 0
fi

if [ ! -f "$FILE" ]; then
  echo "File not found: $FILE"
  exit 0
fi

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
SUGGESTIONS_FILE="$AGENT_DIR/suggestions/${TIMESTAMP}_kairos.json"
ISSUES=()

# ── 파일 확장자별 경량 검사 ──
EXT="${FILE##*.}"

case "$EXT" in
  py)
    # Python: 기본 구문 검사
    if ! python3 -c "import py_compile; py_compile.compile('$FILE', doraise=True)" 2>/dev/null; then
      ISSUES+=("Python syntax error in $FILE")
    fi
    ;;
  js|ts|jsx|tsx)
    # JS/TS: 기본 구문 검사 (node --check)
    if command -v node &>/dev/null; then
      if [[ "$EXT" == "js" ]] && ! node --check "$FILE" 2>/dev/null; then
        ISSUES+=("JavaScript syntax error in $FILE")
      fi
    fi
    ;;
  json)
    # JSON: 파싱 검사
    if ! python3 -c "import json; json.load(open('$FILE'))" 2>/dev/null; then
      ISSUES+=("Invalid JSON in $FILE")
    fi
    ;;
  md)
    # Markdown: 빈 파일 검사
    if [ ! -s "$FILE" ]; then
      ISSUES+=("Empty markdown file: $FILE")
    fi
    ;;
  sh)
    # Shell: 구문 검사
    if ! bash -n "$FILE" 2>/dev/null; then
      ISSUES+=("Shell syntax error in $FILE")
    fi
    ;;
esac

# ── 공통 검사 ──
# 민감 정보 패턴 검사 (api_key, password, token + AWS_ACCESS_KEY_ID, PRIVATE_KEY, SECRET_KEY)
if grep -qiE '(api_key|api_secret|password|token|AWS_ACCESS_KEY_ID|PRIVATE_KEY|SECRET_KEY)\s*[:=]\s*["'"'"'][A-Za-z0-9]' "$FILE" 2>/dev/null; then
  ISSUES+=("Potential hardcoded credential in $FILE")
fi

# ── 결과 출력 ──
if [ ${#ISSUES[@]} -gt 0 ]; then
  # 안전한 JSON 생성: ISSUES를 임시 파일에 쓰고 python3에서 읽기
  ISSUES_TMP="$(mktemp)"
  for issue in "${ISSUES[@]}"; do
    echo "$issue" >> "$ISSUES_TMP"
  done

  export KAIROS_TIMESTAMP="$TIMESTAMP" KAIROS_FILE="$FILE" KAIROS_ISSUES_FILE="$ISSUES_TMP"
  python3 -c "
import json, os

with open(os.environ['KAIROS_ISSUES_FILE']) as f:
    issues = [line.strip() for line in f if line.strip()]

result = {
    'timestamp': os.environ['KAIROS_TIMESTAMP'],
    'file': os.environ['KAIROS_FILE'],
    'issues': issues,
    'severity': 'warn'
}
print(json.dumps(result, ensure_ascii=False, indent=2))
" | tee "$SUGGESTIONS_FILE"

  rm -f "$ISSUES_TMP"
else
  echo "KAIROS: $FILE — no issues found"
fi
