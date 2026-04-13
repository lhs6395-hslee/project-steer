"""Smoke tests for Harness Pipeline.

Validates:
- All agent scripts exist and are executable
- JSON schema files are valid
- Cross-platform configuration files exist

Requirements: 31.1, 23.5, 23.6
"""

import json
import os
import stat

import pytest

from tests.conftest import AGENTS_DIR, PROJECT_ROOT, SCHEMAS_DIR, SCRIPTS_DIR


# ── Agent script existence and executability ──

AGENT_SCRIPTS = [
    "agent_team.sh",
    "auto_dream.sh",
    "call_agent.sh",
    "confidence_trigger.sh",
    "git_worktree.sh",
    "guardian.sh",
    "harness_subtraction.sh",
    "ide_adapter.sh",
    "kairos.sh",
    "sdd_integrator.sh",
    "sync_pipeline.sh",
    "token_tracker.sh",
    "ultraplan.sh",
]

ORCHESTRATOR_SCRIPTS = [
    "orchestrate.sh",
    "mcp-toggle.sh",
]


class TestScriptExistence:
    """All agent scripts must exist."""

    @pytest.mark.parametrize("script", AGENT_SCRIPTS)
    def test_agent_script_exists(self, script):
        path = os.path.join(AGENTS_DIR, script)
        assert os.path.isfile(path), f"Agent script missing: {path}"

    @pytest.mark.parametrize("script", ORCHESTRATOR_SCRIPTS)
    def test_orchestrator_script_exists(self, script):
        path = os.path.join(SCRIPTS_DIR, script)
        assert os.path.isfile(path), f"Orchestrator script missing: {path}"

    @pytest.mark.parametrize("script", AGENT_SCRIPTS)
    def test_agent_script_has_shebang(self, script):
        path = os.path.join(AGENTS_DIR, script)
        with open(path) as f:
            first_line = f.readline()
        assert first_line.startswith("#!/bin/bash"), f"{script} missing bash shebang"


# ── JSON schema validity ──

SCHEMA_FILES = [
    "sprint_contract.schema.json",
    "verdict.schema.json",
    "handoff_file.schema.json",
]


class TestSchemaValidity:
    """JSON schema files must be valid JSON."""

    @pytest.mark.parametrize("schema_file", SCHEMA_FILES)
    def test_schema_is_valid_json(self, schema_file):
        path = os.path.join(SCHEMAS_DIR, schema_file)
        assert os.path.isfile(path), f"Schema file missing: {path}"
        with open(path) as f:
            data = json.load(f)
        assert "type" in data, f"Schema {schema_file} missing 'type' field"
        assert "properties" in data, f"Schema {schema_file} missing 'properties' field"

    @pytest.mark.parametrize("schema_file", SCHEMA_FILES)
    def test_schema_has_required_fields(self, schema_file):
        path = os.path.join(SCHEMAS_DIR, schema_file)
        with open(path) as f:
            data = json.load(f)
        assert "required" in data, f"Schema {schema_file} missing 'required' field"
        assert len(data["required"]) > 0, f"Schema {schema_file} has empty 'required'"


# ── Cross-platform configuration files ──

CONFIG_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    ".mcp.json",
]

CONFIG_DIRS = [
    ".kiro",
    ".gemini",
    ".agent",
]


class TestCrossPlatformConfig:
    """Cross-platform configuration files and directories must exist."""

    @pytest.mark.parametrize("config_file", CONFIG_FILES)
    def test_config_file_exists(self, config_file):
        path = os.path.join(PROJECT_ROOT, config_file)
        assert os.path.isfile(path), f"Config file missing: {path}"

    @pytest.mark.parametrize("config_dir", CONFIG_DIRS)
    def test_config_dir_exists(self, config_dir):
        path = os.path.join(PROJECT_ROOT, config_dir)
        assert os.path.isdir(path), f"Config directory missing: {path}"

    def test_kiro_steering_exists(self):
        path = os.path.join(PROJECT_ROOT, ".kiro", "steering")
        assert os.path.isdir(path), "Kiro steering directory missing"

    def test_kiro_mcp_config_exists(self):
        path = os.path.join(PROJECT_ROOT, ".kiro", "settings", "mcp.json")
        assert os.path.isfile(path), "Kiro MCP config missing"
        with open(path) as f:
            data = json.load(f)
        assert "mcpServers" in data

    def test_token_budget_config_exists(self):
        path = os.path.join(PROJECT_ROOT, "config", "token_budget.json")
        assert os.path.isfile(path), "Token budget config missing"
        with open(path) as f:
            data = json.load(f)
        assert "max_tokens" in data
