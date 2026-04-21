#!/bin/bash
exec 2>>/Users/toule/Documents/kiro/project-steer/.pipeline/workspace_mcp_debug.log
echo "$(date): started, PATH=$PATH" >&2
/Users/toule/.local/bin/uvx workspace-mcp --single-user
echo "$(date): exited $?" >&2
