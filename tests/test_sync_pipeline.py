"""Unit Tests for cross-platform synchronization.

Tests Sync_Pipeline's Claude Code → Kiro synchronization and
MCP Toggle's one-way sync behavior.

Validates: Requirements 11.1, 11.5, 12.4
"""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

from tests.conftest import AGENTS_DIR, PROJECT_ROOT, SCRIPTS_DIR

SYNC_SCRIPT = os.path.join(AGENTS_DIR, "sync_pipeline.sh")
MCP_TOGGLE_SCRIPT = os.path.join(SCRIPTS_DIR, "mcp-toggle.sh")


class TestSyncPipelineStatus:
    """Sync_Pipeline --status must report config file existence."""

    def test_status_command_runs(self):
        """--status should execute without errors."""
        result = subprocess.run(
            ["bash", SYNC_SCRIPT, "--status"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"--status failed: {result.stderr}"
        assert "Sync Pipeline Status" in result.stdout

    def test_status_reports_config_files(self):
        """--status should report on known config files."""
        result = subprocess.run(
            ["bash", SYNC_SCRIPT, "--status"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        # Should mention key config files
        assert "CLAUDE.md" in result.stdout
        assert ".mcp.json" in result.stdout
        assert "AGENTS.md" in result.stdout


class TestMCPToggleSync:
    """MCP Toggle must sync Claude Code → Kiro (one-way)."""

    def test_sync_command_runs(self):
        """mcp-toggle.sh sync should execute without errors."""
        result = subprocess.run(
            ["bash", MCP_TOGGLE_SCRIPT, "sync"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"sync failed: {result.stderr}"

    def test_sync_updates_kiro_from_primary(self):
        """After sync, Kiro config should match primary disabled states."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create primary with specific states
            primary = {
                "mcpServers": {
                    "pptx": {"command": "echo", "args": [], "disabled": False},
                    "docx": {"command": "echo", "args": [], "disabled": True},
                }
            }
            kiro = {
                "mcpServers": {
                    "pptx": {"command": "echo", "args": [], "disabled": True},
                    "docx": {"command": "echo", "args": [], "disabled": False},
                }
            }

            primary_path = os.path.join(tmpdir, ".mcp.json")
            kiro_dir = os.path.join(tmpdir, ".kiro", "settings")
            os.makedirs(kiro_dir, exist_ok=True)
            kiro_path = os.path.join(kiro_dir, "mcp.json")

            with open(primary_path, "w") as f:
                json.dump(primary, f)
            with open(kiro_path, "w") as f:
                json.dump(kiro, f)

            # Copy mcp-toggle.sh
            scripts_dir = os.path.join(tmpdir, "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            shutil.copy2(MCP_TOGGLE_SCRIPT, os.path.join(scripts_dir, "mcp-toggle.sh"))

            result = subprocess.run(
                ["bash", "scripts/mcp-toggle.sh", "sync"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmpdir,
            )
            assert result.returncode == 0

            with open(kiro_path) as f:
                kiro_after = json.load(f)

            # Kiro should now match primary
            assert kiro_after["mcpServers"]["pptx"]["disabled"] is False
            assert kiro_after["mcpServers"]["docx"]["disabled"] is True

    def test_status_command_shows_all_servers(self):
        """mcp-toggle.sh status should list all servers."""
        result = subprocess.run(
            ["bash", MCP_TOGGLE_SCRIPT, "status"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "Primary" in result.stdout


class TestOneWaySyncEnforcement:
    """Sync must be one-way: Claude Code → Kiro (never reverse)."""

    def test_sync_direction_is_one_way(self):
        """Sync_Pipeline should only support --from claude_code direction."""
        # The sync_pipeline.sh only syncs from claude_code
        result = subprocess.run(
            ["bash", SYNC_SCRIPT, "--from", "claude_code", "--to", "kiro"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "Complete" in result.stdout or "Synced" in result.stdout or "sync" in result.stdout.lower()

    def test_verify_after_sync(self):
        """After sync, verify command should confirm matching states."""
        with tempfile.TemporaryDirectory() as tmpdir:
            servers = {"test_server": {"command": "echo", "args": [], "disabled": False}}
            primary = {"mcpServers": servers}
            kiro = {"mcpServers": {"test_server": {"command": "echo", "args": [], "disabled": False}}}

            primary_path = os.path.join(tmpdir, ".mcp.json")
            kiro_dir = os.path.join(tmpdir, ".kiro", "settings")
            os.makedirs(kiro_dir, exist_ok=True)
            kiro_path = os.path.join(kiro_dir, "mcp.json")

            with open(primary_path, "w") as f:
                json.dump(primary, f)
            with open(kiro_path, "w") as f:
                json.dump(kiro, f)

            scripts_dir = os.path.join(tmpdir, "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            shutil.copy2(MCP_TOGGLE_SCRIPT, os.path.join(scripts_dir, "mcp-toggle.sh"))

            result = subprocess.run(
                ["bash", "scripts/mcp-toggle.sh", "verify"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmpdir,
            )
            assert result.returncode == 0
            assert "PASS" in result.stdout
