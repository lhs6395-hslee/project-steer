#!/bin/bash
# Sync_Pipeline — IDE 간 다방향 설정 변환
# Claude Code ↔ Kiro ↔ Antigravity ↔ VS Code
#
# Usage:
#   bash scripts/agents/sync_pipeline.sh --from claude_code --to kiro
#   bash scripts/agents/sync_pipeline.sh --from claude_code --to all
#   bash scripts/agents/sync_pipeline.sh --status

set -euo pipefail

source "$(dirname "$0")/ide_adapter.sh"

ACTION="${1:---status}"

show_status() {
  echo "=== Sync Pipeline Status ==="
  echo "Current IDE: $IDE_NAME"
  echo ""
  echo "Config files:"
  [ -f "CLAUDE.md" ] && echo "  ✅ CLAUDE.md" || echo "  ❌ CLAUDE.md"
  [ -f ".mcp.json" ] && echo "  ✅ .mcp.json" || echo "  ❌ .mcp.json"
  [ -f ".claude/settings.json" ] && echo "  ✅ .claude/settings.json" || echo "  ❌ .claude/settings.json"
  [ -f "AGENTS.md" ] && echo "  ✅ AGENTS.md" || echo "  ❌ AGENTS.md"
  [ -f ".kiro/settings/mcp.json" ] && echo "  ✅ .kiro/settings/mcp.json" || echo "  ❌ .kiro/settings/mcp.json"
  [ -d ".kiro/steering" ] && echo "  ✅ .kiro/steering/" || echo "  ❌ .kiro/steering/"
  [ -f ".gemini/GEMINI.md" ] && echo "  ✅ .gemini/GEMINI.md" || echo "  ❌ .gemini/GEMINI.md"
  [ -d ".agent/rules" ] && echo "  ✅ .agent/rules/" || echo "  ❌ .agent/rules/"
  [ -d ".agent/workflows" ] && echo "  ✅ .agent/workflows/" || echo "  ❌ .agent/workflows/"
}

sync_mcp() {
  local target="$1"
  case "$target" in
    kiro)
      bash scripts/mcp-toggle.sh sync
      ;;
    all)
      bash scripts/mcp-toggle.sh sync
      # Antigravity/VS Code는 .mcp.json을 직접 읽으므로 추가 동기화 불필요
      ;;
  esac
}

sync_hooks() {
  local target="$1"
  # Claude Code hooks → 다른 IDE 포맷으로 변환
  if [ -f ".claude/settings.json" ]; then
    echo "[sync] Hooks: .claude/settings.json detected"
    case "$target" in
      kiro)
        echo "[sync] Kiro hooks are managed via createHook tool — manual sync"
        ;;
      antigravity)
        echo "[sync] Antigravity workflows in .agent/workflows/ — manual sync"
        ;;
    esac
  fi
}

case "$ACTION" in
  --status)
    show_status
    ;;
  --from)
    FROM="${2:?--from requires IDE name}"
    shift 2
    TO_FLAG="${1:?--to required}"
    TO="${2:?--to requires IDE name or 'all'}"
    echo "=== Sync: $FROM → $TO ==="
    sync_mcp "$TO"
    sync_hooks "$TO"
    echo "[sync] Complete"
    ;;
  *)
    echo "Usage:"
    echo "  bash scripts/agents/sync_pipeline.sh --status"
    echo "  bash scripts/agents/sync_pipeline.sh --from claude_code --to kiro"
    echo "  bash scripts/agents/sync_pipeline.sh --from claude_code --to all"
    ;;
esac
