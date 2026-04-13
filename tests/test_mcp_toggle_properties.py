"""Property-Based Tests for MCP Toggle state synchronization.

Feature: harness-pipeline
Property 10: MCP toggle state synchronization

For any MCP server name and target state (on/off), after executing
mcp-toggle.sh, the disabled field in .mcp.json and .kiro/settings/mcp.json
SHALL have the same value for that server.

Validates: Requirements 12.4
"""

import json
import os
import shutil
import subprocess
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import PROJECT_ROOT, SCRIPTS_DIR

MCP_TOGGLE_SCRIPT = os.path.join(SCRIPTS_DIR, "mcp-toggle.sh")

# Servers that exist in both .mcp.json and .kiro/settings/mcp.json
SHARED_SERVERS = ["trello", "datadog", "google-workspace", "docx", "pptx", "dooray"]


def create_test_mcp_env(tmpdir: str, servers: list, initial_disabled: bool = True):
    """Create a test environment with .mcp.json and .kiro/settings/mcp.json."""
    primary = {"mcpServers": {}}
    kiro = {"mcpServers": {}}

    for server in servers:
        primary["mcpServers"][server] = {
            "command": "echo",
            "args": ["test"],
            "disabled": initial_disabled,
        }
        kiro["mcpServers"][server] = {
            "command": "echo",
            "args": ["test"],
            "disabled": initial_disabled,
        }

    primary_path = os.path.join(tmpdir, ".mcp.json")
    kiro_dir = os.path.join(tmpdir, ".kiro", "settings")
    os.makedirs(kiro_dir, exist_ok=True)
    kiro_path = os.path.join(kiro_dir, "mcp.json")

    with open(primary_path, "w") as f:
        json.dump(primary, f, indent=2)
    with open(kiro_path, "w") as f:
        json.dump(kiro, f, indent=2)

    # Copy the mcp-toggle.sh script to tmpdir
    scripts_dir = os.path.join(tmpdir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    shutil.copy2(MCP_TOGGLE_SCRIPT, os.path.join(scripts_dir, "mcp-toggle.sh"))

    return primary_path, kiro_path


class TestMCPToggleSynchronization:
    """Feature: harness-pipeline, Property 10: MCP toggle state synchronization

    For any MCP server name and target state (on/off), after executing
    mcp-toggle.sh, the disabled field in .mcp.json and .kiro/settings/mcp.json
    SHALL have the same value for that server.

    Validates: Requirements 12.4
    """

    @given(
        server=st.sampled_from(SHARED_SERVERS),
        state=st.sampled_from(["on", "off"]),
    )
    @settings(max_examples=100)
    def test_toggle_syncs_disabled_field(self, server, state):
        """After toggle, both config files must have matching disabled state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            primary_path, kiro_path = create_test_mcp_env(tmpdir, SHARED_SERVERS)

            result = subprocess.run(
                ["bash", "scripts/mcp-toggle.sh", server, state],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmpdir,
            )
            assert result.returncode == 0, (
                f"mcp-toggle.sh failed: {result.stderr}"
            )

            with open(primary_path) as f:
                primary = json.load(f)
            with open(kiro_path) as f:
                kiro = json.load(f)

            expected_disabled = state == "off"
            primary_disabled = primary["mcpServers"][server].get("disabled", False)
            kiro_disabled = kiro["mcpServers"][server].get("disabled", False)

            assert primary_disabled == expected_disabled, (
                f"Primary .mcp.json: {server} disabled={primary_disabled}, expected={expected_disabled}"
            )
            assert kiro_disabled == expected_disabled, (
                f"Kiro mcp.json: {server} disabled={kiro_disabled}, expected={expected_disabled}"
            )
            assert primary_disabled == kiro_disabled, (
                f"Mismatch: primary={primary_disabled}, kiro={kiro_disabled}"
            )

    @given(
        server=st.sampled_from(SHARED_SERVERS),
    )
    @settings(max_examples=100)
    def test_verify_command_passes_after_sync(self, server):
        """After toggle + sync, verify command should pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            primary_path, kiro_path = create_test_mcp_env(tmpdir, SHARED_SERVERS)

            # Toggle on
            subprocess.run(
                ["bash", "scripts/mcp-toggle.sh", server, "on"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmpdir,
            )

            # Verify
            result = subprocess.run(
                ["bash", "scripts/mcp-toggle.sh", "verify"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmpdir,
            )
            assert result.returncode == 0, (
                f"verify failed after toggle: {result.stdout}\n{result.stderr}"
            )
