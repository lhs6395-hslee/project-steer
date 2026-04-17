#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# switch-provider.sh — Bedrock / Vertex AI / Direct 전환
#
# Usage:
#   bash scripts/switch-provider.sh bedrock   # AWS Bedrock으로 전환
#   bash scripts/switch-provider.sh vertex    # Vertex AI로 전환
#   bash scripts/switch-provider.sh direct    # Claude 직접 로그인으로 전환
#   bash scripts/switch-provider.sh status    # 현재 상태 확인
# ──────────────────────────────────────────────────────────
set -euo pipefail

GLOBAL_SETTINGS="$HOME/.claude/settings.json"

# ── Profiles ──────────────────────────────────────────────
bedrock_env() {
  # Bedrock 검증된 최신 모델 ID (us-east-1, 2026-04-15 기준)
  cat <<'JSON'
{
  "CLAUDE_CODE_USE_BEDROCK": "1",
  "CLAUDE_CODE_USE_VERTEX": "0",
  "AWS_REGION": "us-east-1",
  "CLOUD_ML_REGION": "global",
  "ANTHROPIC_VERTEX_PROJECT_ID": "architect-hslee-3572",
  "ANTHROPIC_DEFAULT_OPUS_MODEL": "us.anthropic.claude-opus-4-6-v1",
  "ANTHROPIC_DEFAULT_SONNET_MODEL": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  "ANTHROPIC_DEFAULT_HAIKU_MODEL": "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}
JSON
}

vertex_env() {
  # Vertex AI 모델 ID — 공식 문서 기준 (code.claude.com/docs/en/google-vertex-ai)
  # Vertex는 "claude-*" 형식 사용 (Bedrock의 "us.anthropic.*"와 다름)
  cat <<'JSON'
{
  "CLAUDE_CODE_USE_BEDROCK": "0",
  "CLAUDE_CODE_USE_VERTEX": "1",
  "AWS_REGION": "us-east-1",
  "CLOUD_ML_REGION": "global",
  "ANTHROPIC_VERTEX_PROJECT_ID": "architect-hslee-3572",
  "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6",
  "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
  "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5@20251001"
}
JSON
}

direct_env() {
  # Claude 직접 로그인 — Anthropic API (claude.ai 구독 or ANTHROPIC_API_KEY)
  # 공식 문서: code.claude.com/docs/en/claude-code/settings#model-configuration
  # BEDROCK/VERTEX 모두 0, 모델 ID는 Vertex와 동일한 "claude-*" 형식
  cat <<'JSON'
{
  "CLAUDE_CODE_USE_BEDROCK": "0",
  "CLAUDE_CODE_USE_VERTEX": "0",
  "AWS_REGION": "us-east-1",
  "CLOUD_ML_REGION": "global",
  "ANTHROPIC_VERTEX_PROJECT_ID": "architect-hslee-3572",
  "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6",
  "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
  "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001"
}
JSON
}

bedrock_model="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
vertex_model="claude-sonnet-4-6"
direct_model="claude-sonnet-4-6"

# ── Helpers ───────────────────────────────────────────────
require_jq() {
  command -v jq >/dev/null 2>&1 || { echo "ERROR: jq is required. Install: brew install jq"; exit 1; }
}

current_provider() {
  if [[ ! -f "$GLOBAL_SETTINGS" ]]; then
    echo "none"
    return
  fi
  local use_bedrock use_vertex
  use_bedrock=$(jq -r '.env.CLAUDE_CODE_USE_BEDROCK // ""' "$GLOBAL_SETTINGS" 2>/dev/null)
  use_vertex=$(jq -r '.env.CLAUDE_CODE_USE_VERTEX // ""' "$GLOBAL_SETTINGS" 2>/dev/null)
  if [[ "$use_bedrock" == "1" ]]; then echo "bedrock"
  elif [[ "$use_vertex" == "1" ]]; then echo "vertex"
  else echo "direct"
  fi
}

show_status() {
  local provider
  provider=$(current_provider)
  echo "┌─────────────────────────────────────┐"
  echo "│  Claude Code Provider Status        │"
  echo "├─────────────────────────────────────┤"
  printf "│  Active : %-26s│\n" "$provider"
  printf "│  Config : %-26s│\n" "$GLOBAL_SETTINGS"
  echo "├─────────────────────────────────────┤"
  echo "│  env block:                         │"
  jq -r '.env // {} | to_entries[] | "│    \(.key)=\(.value)"' "$GLOBAL_SETTINGS" 2>/dev/null | while IFS= read -r line; do
    printf "%-38s│\n" "$line"
  done
  printf "│  model  : %-26s│\n" "$(jq -r '.model // "default"' "$GLOBAL_SETTINGS" 2>/dev/null)"
  echo "└─────────────────────────────────────┘"
}

switch_to() {
  local target="$1"
  local current
  current=$(current_provider)

  if [[ "$current" == "$target" ]]; then
    echo "Already on $target. No changes made."
    exit 0
  fi

  local new_env new_model
  case "$target" in
    bedrock)
      new_env=$(bedrock_env)
      new_model="$bedrock_model"
      ;;
    vertex)
      new_env=$(vertex_env)
      new_model="$vertex_model"
      # ADC check (force Python 3.10 for gcloud compatibility)
      export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-$(command -v python3.10 2>/dev/null || echo python3)}"
      GCLOUD="${GCLOUD:-$(command -v gcloud 2>/dev/null || echo /opt/homebrew/share/google-cloud-sdk/bin/gcloud)}"
      if ! "$GCLOUD" auth application-default print-access-token >/dev/null 2>&1; then
        echo "WARNING: ADC not configured. Run:"
        echo "  gcloud auth application-default login"
        echo ""
        echo "Switching config anyway (will need ADC before using Claude Code)."
      fi
      ;;
    direct)
      new_env=$(direct_env)
      new_model="$direct_model"
      # claude.ai 로그인 세션 또는 ANTHROPIC_API_KEY 필요
      # 로그인 확인: claude auth status
      if ! command -v claude >/dev/null 2>&1; then
        echo "WARNING: claude CLI not found in PATH."
      fi
      ;;
    *)
      echo "Unknown provider: $target"
      echo "Usage: $0 {bedrock|vertex|direct|status}"
      exit 1
      ;;
  esac

  # Atomic update: read → merge → write
  local tmp
  tmp=$(mktemp)
  if [[ -f "$GLOBAL_SETTINGS" ]]; then
    jq --argjson newenv "$new_env" --arg model "$new_model" '
      .env = $newenv | .model = $model
    ' "$GLOBAL_SETTINGS" > "$tmp"
  else
    jq -n --argjson newenv "$new_env" --arg model "$new_model" '
      { env: $newenv, model: $model }
    ' > "$tmp"
  fi
  mv "$tmp" "$GLOBAL_SETTINGS"

  echo "Switched: $current -> $target"
  echo ""
  show_status
  echo ""
  echo "Restart Claude Code to apply changes."
}

# ── Main ──────────────────────────────────────────────────
require_jq

case "${1:-status}" in
  bedrock) switch_to bedrock ;;
  vertex)  switch_to vertex ;;
  direct)  switch_to direct ;;
  status)  show_status ;;
  *)
    echo "Usage: $0 {bedrock|vertex|direct|status}"
    exit 1
    ;;
esac
