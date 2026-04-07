#!/bin/bash
# Sync Claude Code settings to Kiro/Antigravity
# Triggered by Claude Code's FileChanged/PostToolUse hook when config files change

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# 1. Sync MCP settings: .mcp.json → .kiro/settings/mcp.json
if [ -f "$PROJECT_DIR/.mcp.json" ] && [ -f "$PROJECT_DIR/.kiro/settings/mcp.json" ]; then
  python3 -c "
import json

with open('$PROJECT_DIR/.mcp.json') as f:
    primary = json.load(f)
with open('$PROJECT_DIR/.kiro/settings/mcp.json') as f:
    kiro = json.load(f)

changed = False
for name, cfg in primary.get('mcpServers', {}).items():
    if name in kiro.get('mcpServers', {}):
        if kiro['mcpServers'][name].get('disabled') != cfg.get('disabled', False):
            kiro['mcpServers'][name]['disabled'] = cfg.get('disabled', False)
            changed = True

if changed:
    with open('$PROJECT_DIR/.kiro/settings/mcp.json', 'w') as f:
        json.dump(kiro, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print('[sync] .mcp.json → .kiro/settings/mcp.json')
"
fi

# 2. Sync user-level Kiro MCP
KIRO_USER="$HOME/.kiro/settings/mcp.json"
if [ -f "$PROJECT_DIR/.mcp.json" ] && [ -f "$KIRO_USER" ]; then
  python3 -c "
import json, os

NAME_MAP = {'pptx': 'pptx', 'docx': 'docx', 'trello': 'trello',
            'datadog': 'datadog', 'dooray': 'dooray', 'google-workspace': 'google-workspace'}

with open('$PROJECT_DIR/.mcp.json') as f:
    primary = json.load(f)
with open('$KIRO_USER') as f:
    user = json.load(f)

changed = False
for name, cfg in primary.get('mcpServers', {}).items():
    user_name = NAME_MAP.get(name, name)
    if user_name in user.get('mcpServers', {}):
        if user['mcpServers'][user_name].get('disabled') != cfg.get('disabled', False):
            user['mcpServers'][user_name]['disabled'] = cfg.get('disabled', False)
            changed = True

if changed:
    with open('$KIRO_USER', 'w') as f:
        json.dump(user, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print('[sync] .mcp.json → ~/.kiro/settings/mcp.json')
"
fi

# 3. Sync AGENTS.md content to .gemini/GEMINI.md (keep Antigravity in sync)
# AGENTS.md is the universal source — no action needed, Antigravity reads it directly
