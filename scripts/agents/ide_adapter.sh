#!/bin/bash
# IDE_Adapter — 런타임 IDE 환경 감지 및 경로 매핑
#
# Usage:
#   source scripts/agents/ide_adapter.sh
#   echo $IDE_NAME $AGENT_DIR $HOOKS_DIR $STEERING_DIR

# ── IDE 감지 ──
detect_ide() {
  if [ -n "${CLAUDE_CODE:-}" ] || command -v claude &>/dev/null; then
    echo "claude_code"
  elif [ -n "${KIRO_IDE:-}" ] || [ -d ".kiro/" ]; then
    echo "kiro"
  elif [ -n "${ANTIGRAVITY:-}" ] || [ -d ".antigravity/" ]; then
    echo "antigravity"
  elif [ -n "${VSCODE_PID:-}" ] || [ -d ".vscode/" ]; then
    echo "vscode"
  elif [ -n "${CLAUDE_DESKTOP:-}" ]; then
    echo "claude_desktop"
  else
    echo "WARNING: No IDE detected — defaulting to kiro" >&2
    echo "kiro"  # 기본값
  fi
}

IDE_NAME=$(detect_ide)

# ── IDE별 경로 매핑 ──
case "$IDE_NAME" in
  claude_code)
    AGENT_DIR=".pipeline"
    HOOKS_DIR=".claude/hooks"
    STEERING_DIR="."
    CONFIG_FILE="CLAUDE.md"
    MCP_FILE=".mcp.json"
    ;;
  kiro)
    AGENT_DIR=".pipeline"
    HOOKS_DIR=".kiro/hooks"
    STEERING_DIR=".kiro/steering"
    CONFIG_FILE="AGENTS.md"
    MCP_FILE=".kiro/settings/mcp.json"
    ;;
  antigravity)
    AGENT_DIR=".pipeline"
    HOOKS_DIR=".agent/workflows"
    STEERING_DIR=".agent/rules"
    CONFIG_FILE="AGENTS.md"
    MCP_FILE=".mcp.json"
    ;;
  vscode)
    AGENT_DIR=".pipeline"
    HOOKS_DIR=".vscode"
    STEERING_DIR=".vscode"
    CONFIG_FILE="AGENTS.md"
    MCP_FILE=".mcp.json"
    ;;
  claude_desktop)
    AGENT_DIR=".pipeline"
    HOOKS_DIR=""
    STEERING_DIR=""
    CONFIG_FILE="CLAUDE.md"
    MCP_FILE=".mcp.json"
    ;;
esac

# ── 에이전트 디렉토리 구조 생성 ──
ensure_agent_dirs() {
  local base="${1:-$AGENT_DIR}"
  mkdir -p "$base"/{requests,contracts,outputs,verdicts,results,plans,suggestions,metrics,reports,archive}
}

# ── Atomic Write ──
atomic_write() {
  local target="$1"
  local content="$2"
  local tmp="${target}.tmp.$$"
  printf '%s\n' "$content" > "$tmp"
  mv "$tmp" "$target"
}

export IDE_NAME AGENT_DIR HOOKS_DIR STEERING_DIR CONFIG_FILE MCP_FILE
