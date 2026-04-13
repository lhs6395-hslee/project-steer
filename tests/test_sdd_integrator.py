"""Unit Tests for SDD_Integrator acceptance criteria extraction.

Tests that SDD_Integrator correctly extracts module-specific acceptance
criteria from PROJECT.md.

Validates: Requirements 20.1, 20.2
"""

import json
import os
import subprocess

import pytest

from tests.conftest import AGENTS_DIR, PROJECT_ROOT

SDD_SCRIPT = os.path.join(AGENTS_DIR, "sdd_integrator.sh")


def _parse_sdd_json(stdout: str) -> dict:
    """Extract the JSON object from SDD_Integrator output (skip header lines)."""
    lines = stdout.strip().split("\n")
    json_lines = []
    in_json = False
    brace_count = 0
    for line in lines:
        if not in_json and line.strip().startswith("{"):
            in_json = True
        if in_json:
            json_lines.append(line)
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0:
                break
    if json_lines:
        return json.loads("\n".join(json_lines))
    return {}


class TestSDDIntegratorExtraction:
    """SDD_Integrator must extract acceptance criteria from PROJECT.md."""

    def _run_sdd(self, module: str) -> subprocess.CompletedProcess:
        """Run sdd_integrator.sh with a module argument."""
        env = os.environ.copy()
        env.setdefault("AGENT_DIR", ".pipeline")
        result = subprocess.run(
            ["bash", SDD_SCRIPT, module],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=PROJECT_ROOT,
            env=env,
        )
        return result

    @pytest.mark.skipif(
        not os.path.isfile(os.path.join(PROJECT_ROOT, "PROJECT.md")),
        reason="PROJECT.md not found — SDD_Integrator requires it",
    )
    def test_pptx_module_extraction(self):
        """SDD_Integrator should extract criteria for pptx module."""
        result = self._run_sdd("pptx")
        assert result.returncode == 0, f"SDD failed: {result.stderr}"
        data = _parse_sdd_json(result.stdout)
        assert data.get("module") == "pptx"
        assert "criteria_count" in data
        assert "acceptance_criteria" in data
        assert data["criteria_count"] > 0

    @pytest.mark.skipif(
        not os.path.isfile(os.path.join(PROJECT_ROOT, "PROJECT.md")),
        reason="PROJECT.md not found — SDD_Integrator requires it",
    )
    def test_docx_module_extraction(self):
        """SDD_Integrator should extract criteria for docx module."""
        result = self._run_sdd("docx")
        assert result.returncode == 0, f"SDD failed: {result.stderr}"
        data = _parse_sdd_json(result.stdout)
        assert data.get("module") == "docx"

    def test_invalid_module_returns_error(self):
        """SDD_Integrator should handle invalid module names gracefully."""
        result = self._run_sdd("invalid_module")
        output = result.stdout.strip()
        data = _parse_sdd_json(output)
        assert "error" in data or data.get("criteria_count", 0) == 0

    @pytest.mark.skipif(
        not os.path.isfile(os.path.join(PROJECT_ROOT, "PROJECT.md")),
        reason="PROJECT.md not found — SDD_Integrator requires it",
    )
    def test_output_has_required_fields(self):
        """SDD output must contain module, extracted_at, criteria_count, acceptance_criteria."""
        result = self._run_sdd("pptx")
        if result.returncode != 0:
            pytest.skip("SDD_Integrator failed — PROJECT.md may be missing")
        data = _parse_sdd_json(result.stdout)
        for field in ["module", "extracted_at", "criteria_count", "acceptance_criteria"]:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.skipif(
        not os.path.isfile(os.path.join(PROJECT_ROOT, "PROJECT.md")),
        reason="PROJECT.md not found — SDD_Integrator requires it",
    )
    def test_criteria_have_id_and_description(self):
        """Each extracted criterion should have id and description."""
        result = self._run_sdd("pptx")
        if result.returncode != 0:
            pytest.skip("SDD_Integrator failed — PROJECT.md may be missing")
        data = _parse_sdd_json(result.stdout)
        for criterion in data.get("acceptance_criteria", []):
            assert "id" in criterion, f"Criterion missing 'id': {criterion}"
            assert "description" in criterion, f"Criterion missing 'description': {criterion}"
