#!/usr/bin/env bash
# Bedrock 모델 에러 감지 시 자동 복구

RECOVERY_SCRIPT="$HOME/Documents/kiro/project-steer/scripts/switch-provider.sh"
SETTINGS="$HOME/.claude/settings.json"

# Stop reason 확인 — 환경변수로 전달됨
STOP_REASON="${CLAUDE_STOP_HOOK_REASON:-}"
STOP_ERROR="${CLAUDE_STOP_HOOK_ERROR:-}"

# Bedrock 모델 에러 패턴 감지
if echo "$STOP_ERROR" | grep -qi "model identifier is invalid" 2>/dev/null || \
   echo "$STOP_REASON" | grep -qi "model identifier is invalid" 2>/dev/null; then
    echo "" >&2
    echo "⚠️  Bedrock 모델 에러로 세션 종료됨" >&2
    echo "────────────────────────────────────" >&2
    echo "자동 복구 옵션:" >&2
    echo "  1. Vertex로 전환:  bash $RECOVERY_SCRIPT vertex" >&2
    echo "  2. 모델 선택:      /model  (Claude Code 재시작 후)" >&2
    echo "  3. 현재 상태:      bash $RECOVERY_SCRIPT status" >&2
    echo "" >&2
    
    # Vertex로 자동 전환 (선택적)
    if [[ -f "$RECOVERY_SCRIPT" ]]; then
        bash "$RECOVERY_SCRIPT" vertex >/dev/null 2>&1 && \
        echo "✅ Vertex AI로 자동 전환 완료. Claude Code를 다시 시작하세요." >&2
    fi
fi
