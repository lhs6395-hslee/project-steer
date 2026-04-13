#!/bin/bash
# MCP Server Toggle — One-way sync from Claude Code to other platforms
#
# Primary: .mcp.json (Claude Code)
# Sync targets: .kiro/settings/mcp.json (Kiro)
#
# Flow: Claude Code → Kiro/Antigravity (never reverse)
#
# Usage:
#   bash scripts/mcp-toggle.sh datadog on
#   bash scripts/mcp-toggle.sh pptx off
#   bash scripts/mcp-toggle.sh status

set -euo pipefail

PRIMARY=".mcp.json"
KIRO_MCP=".kiro/settings/mcp.json"
KIRO_USER_MCP="$HOME/.kiro/settings/mcp.json"

if [ ! -f "$PRIMARY" ]; then
  echo "ERROR: Primary config not found: $PRIMARY"
  exit 1
fi

ACTION="${1:?Usage: mcp-toggle.sh <server|status|sync> [on|off]}"

# Status command
if [ "$ACTION" = "status" ]; then
  echo "Primary: $PRIMARY (Claude Code)"
  echo ""
  python3 -c "
import json
with open('$PRIMARY') as f:
    data = json.load(f)
for name, cfg in data.get('mcpServers', {}).items():
    state = 'OFF' if cfg.get('disabled', False) else 'ON'
    print(f'  {name:20s} {state}')
"
  exit 0
fi

# Sync command — push Claude Code state to Kiro
if [ "$ACTION" = "sync" ]; then
  if [ ! -f "$KIRO_MCP" ]; then
    echo "No Kiro config to sync to"
    exit 0
  fi
  python3 -c "
import json

with open('$PRIMARY') as f:
    primary = json.load(f)
with open('$KIRO_MCP') as f:
    kiro = json.load(f)

for name, cfg in primary.get('mcpServers', {}).items():
    if name in kiro.get('mcpServers', {}):
        kiro['mcpServers'][name]['disabled'] = cfg.get('disabled', False)

with open('$KIRO_MCP', 'w') as f:
    json.dump(kiro, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('Synced Claude Code → Kiro')
"
  exit 0
fi

# Verify command — check that Primary and Kiro disabled fields match
if [ "$ACTION" = "verify" ]; then
  if [ ! -f "$KIRO_MCP" ]; then
    echo "No Kiro config to verify against"
    exit 1
  fi
  python3 -c "
import json, sys

with open('$PRIMARY') as f:
    primary = json.load(f)
with open('$KIRO_MCP') as f:
    kiro = json.load(f)

mismatches = []
for name, cfg in primary.get('mcpServers', {}).items():
    if name in kiro.get('mcpServers', {}):
        p_disabled = cfg.get('disabled', False)
        k_disabled = kiro['mcpServers'][name].get('disabled', False)
        if p_disabled != k_disabled:
            mismatches.append(f'  {name}: primary={p_disabled}, kiro={k_disabled}')

if mismatches:
    print('FAIL: Disabled field mismatch between primary and Kiro:')
    for m in mismatches:
        print(m)
    sys.exit(1)
else:
    print('PASS: All shared servers have matching disabled state')
"
  exit $?
fi

# Toggle command — update primary, then sync
SERVER="$ACTION"
STATE="${2:?Usage: mcp-toggle.sh <server> <on|off>}"

if [[ "$STATE" != "on" && "$STATE" != "off" ]]; then
  echo "ERROR: State must be 'on' or 'off'"
  exit 1
fi

DISABLED=$( [ "$STATE" = "off" ] && echo "True" || echo "False" )

# 1. Update primary (Claude Code)
python3 -c "
import json
with open('$PRIMARY') as f:
    data = json.load(f)
servers = data.get('mcpServers', {})
if '$SERVER' not in servers:
    print('ERROR: Server \"$SERVER\" not found')
    print('Available:', ', '.join(servers.keys()))
    exit(1)
servers['$SERVER']['disabled'] = $DISABLED
with open('$PRIMARY', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
print(f'  $PRIMARY: $SERVER → $STATE')
"

# 2. Sync to Kiro workspace (one-way)
if [ -f "$KIRO_MCP" ]; then
  python3 -c "
import json
with open('$KIRO_MCP') as f:
    data = json.load(f)
servers = data.get('mcpServers', {})
if '$SERVER' in servers:
    servers['$SERVER']['disabled'] = $DISABLED
    with open('$KIRO_MCP', 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f'  $KIRO_MCP: $SERVER → $STATE (synced)')
"
fi

# 3. Sync to Kiro user-level (one-way, with name mapping)
if [ -f "$KIRO_USER_MCP" ]; then
  python3 -c "
import json

# Primary name → user-level name mapping
NAME_MAP = {
    'pptx': 'pptx',
    'docx': 'docx',
    'trello': 'trello',
    'datadog': 'datadog',
    'dooray': 'dooray',
    'google-workspace': 'google-workspace',
}

with open('$KIRO_USER_MCP') as f:
    data = json.load(f)
servers = data.get('mcpServers', {})
user_name = NAME_MAP.get('$SERVER', '$SERVER')
if user_name in servers:
    servers[user_name]['disabled'] = $DISABLED
    with open('$KIRO_USER_MCP', 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f'  ~/.kiro/settings/mcp.json: {user_name} → $STATE (synced)')
"
fi
