#!/bin/bash
# Universal sub-agent caller — detects platform and routes accordingly.
#
# Usage:
#   bash scripts/agents/call_agent.sh <role> <input_file> <output_file> [module]
#
# Supports:
#   - Claude Code: claude --print (native sub-agent)
#   - Kiro: falls back to claude CLI if available, otherwise cat skill as guidance
#   - Antigravity: falls back to gemini CLI if available

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in call_agent.sh (line $LINENO)" >&2; exit 2' ERR

ROLE="${1:?Usage: call_agent.sh <role> <input_file> <output_file> [module]}"
INPUT_FILE="${2:?}"
OUTPUT_FILE="${3:?}"
MODULE="${4:-}"

SKILL_FILE="skills/${ROLE}/SKILL.md"

if [ ! -f "$SKILL_FILE" ]; then
  echo "ERROR: Skill file not found: $SKILL_FILE" >&2
  exit 1
fi

# Build system prompt
SYSTEM_PROMPT="$(cat "$SKILL_FILE")"

if [ "$ROLE" = "executor" ] && [ -n "$MODULE" ] && [ -f "modules/${MODULE}/SKILL.md" ]; then
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

# ─── Platform Detection + Retry Logic (max 2 retries) ───
MAX_RETRIES=2
ATTEMPT=0

call_agent_once() {
  # 1. Claude Code (preferred)
  if command -v claude &>/dev/null; then
    timeout 120 claude --print \
      --system-prompt "$SYSTEM_PROMPT" \
      --output-format json \
      --max-turns 1 \
      "$INPUT" > "$OUTPUT_FILE" 2>/dev/null
    return 0
  fi

  # 2. Gemini CLI (Antigravity)
  if command -v gemini &>/dev/null; then
    echo "$INPUT" | timeout 120 gemini \
      --system-instruction "$SYSTEM_PROMPT" \
      --json > "$OUTPUT_FILE" 2>/dev/null
    return 0
  fi

  # 3. Fallback — output skill + input for manual processing
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
    sleep 1
  fi
done

echo "ERROR: Agent $ROLE failed after $((MAX_RETRIES + 1)) attempts" >&2
exit 2
