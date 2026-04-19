#!/usr/bin/env bash
# pipeline-check.sh — Stop hook: 파이프라인 준수 여부 경고 출력 (prompt loop 없음)
#
# 입력: stdin으로 hook 입력 JSON (stop_hook_active 포함)
# 출력: 위반 감지 시 경고 메시지 출력 (exit 0, Claude 응답 유발 안 함)
#
# type: command 방식이므로 Claude에게 프롬프트를 보내지 않음.
# → 무한 루프 방지

INPUT=$(cat)

# stop_hook_active 플래그 확인 (이미 hook 안에 있으면 스킵)
ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)
if [[ "$ACTIVE" == "true" ]]; then
  exit 0
fi

# 트랜스크립트에서 마지막 assistant 메시지 추출
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript // ""' 2>/dev/null)

# pptx/docx/dooray 등 모듈 작업 키워드 탐지
MODULE_KEYWORDS="pptx|docx|dooray|gdrive|datadog|wbs|trello"
HAS_MODULE=$(echo "$TRANSCRIPT" | grep -iE "$MODULE_KEYWORDS" | head -1)

if [[ -z "$HAS_MODULE" ]]; then
  # 모듈 작업 없음 — 파이프라인 체크 불필요
  exit 0
fi

# @planner / @executor / @reviewer 사용 여부 확인
HAS_PLANNER=$(echo "$TRANSCRIPT" | grep -E "@planner|subagent_type.*planner|\"planner\"" | head -1)
HAS_EXECUTOR=$(echo "$TRANSCRIPT" | grep -E "@executor|subagent_type.*executor|\"executor\"" | head -1)
HAS_REVIEWER=$(echo "$TRANSCRIPT" | grep -E "@reviewer|subagent_type.*reviewer|\"reviewer\"" | head -1)

MISSING=""
[[ -z "$HAS_PLANNER" ]] && MISSING="planner "
[[ -z "$HAS_EXECUTOR" ]] && MISSING="${MISSING}executor "
[[ -z "$HAS_REVIEWER" ]] && MISSING="${MISSING}reviewer"

if [[ -n "$MISSING" ]]; then
  echo "⚠️  [Pipeline Check] 모듈 작업에서 파이프라인 미사용: 누락=${MISSING}" >&2
  echo "   CLAUDE.md 규칙: @planner → @executor → @reviewer 필수" >&2
fi

exit 0
