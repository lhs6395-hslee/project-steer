#!/bin/bash
# Claude Code Vertex AI wrapper for VS Code extension
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=global
export ANTHROPIC_VERTEX_PROJECT_ID=architect-hslee-3572
export CLOUDSDK_PYTHON=$(command -v python3.10 2>/dev/null || echo python3)

# Kiro IDE 환경(백그라운드)에서 gcloud 및 시스템 경로를 찾지 못해 인증이 풀리는 현상 방지
export PATH="/opt/homebrew/bin:/usr/local/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

# 문제 원인 파악을 위한 자동 진단 센서
LOG_FILE="/tmp/claude_vertex_wrapper.log"
echo "=== [$(date)] Executing Claude Code ===" >> "$LOG_FILE"
echo "PATH: $PATH" >> "$LOG_FILE"
gcloud auth application-default print-access-token >/dev/null 2>&1 || echo "ERROR: gcloud 명령어를 실행할 수 없거나 토큰 갱신에 실패했습니다." >> "$LOG_FILE"

exec claude "$@"
