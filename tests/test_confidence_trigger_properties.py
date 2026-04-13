"""Property-Based Tests for Confidence_Trigger agent.

Feature: harness-pipeline
Property 4: Confidence_Trigger score calculation and mode mapping
Property 5: Confidence_Trigger enforces full pipeline for security tasks

Validates: Requirements 8.2, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

import json
import subprocess

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from tests.conftest import AGENTS_DIR, PROJECT_ROOT

CT_SCRIPT = f"{AGENTS_DIR}/confidence_trigger.sh"

VALID_MODULES = ["pptx", "docx", "wbs", "trello", "dooray", "gdrive", "datadog"]

SECURITY_KEYWORDS = [
    "인증", "auth", "권한", "permission", "암호",
    "encrypt", "key", "secret", "delete", "삭제",
]


def run_confidence_trigger(task: str, module: str) -> dict:
    """Run confidence_trigger.sh and parse JSON output."""
    result = subprocess.run(
        ["bash", CT_SCRIPT, task, module],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, (
        f"confidence_trigger.sh failed: {result.stderr}"
    )
    return json.loads(result.stdout.strip())


# ── Property 4: Score calculation and mode mapping ──


class TestConfidenceTriggerScoreAndMode:
    """Feature: harness-pipeline, Property 4: Confidence_Trigger score calculation and mode mapping

    For any task description string and valid module name, the Confidence_Trigger
    SHALL produce a score in [0.0, 1.0] with all four dimension scores each in
    [0.0, 1.0], and the resulting mode SHALL match the defined mapping.

    Validates: Requirements 8.2, 9.2, 9.3, 9.4, 9.5, 9.6
    """

    @given(
        task=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "Z", "P"),
                blacklist_characters="\x00'\"\\`$",
            ),
            min_size=1,
            max_size=100,
        ),
        module=st.sampled_from(VALID_MODULES),
    )
    @settings(max_examples=100)
    def test_score_in_valid_range(self, task, module):
        """Score and all dimensions must be in [0.0, 1.0]."""
        assume(task.strip())
        data = run_confidence_trigger(task, module)

        assert 0.0 <= data["score"] <= 1.0, f"Score out of range: {data['score']}"
        dims = data["dimensions"]
        for dim_name in ["ambiguity", "domain_complexity", "stakes", "context_dependency"]:
            assert 0.0 <= dims[dim_name] <= 1.0, (
                f"{dim_name} out of range: {dims[dim_name]}"
            )

    @given(
        task=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "Z", "P"),
                blacklist_characters="\x00'\"\\`$",
            ),
            min_size=1,
            max_size=100,
        ),
        module=st.sampled_from(VALID_MODULES),
    )
    @settings(max_examples=100)
    def test_mode_matches_score_mapping(self, task, module):
        """Mode must match the score-to-mode mapping rules."""
        assume(task.strip())
        data = run_confidence_trigger(task, module)
        score = data["score"]
        mode = data["mode"]
        max_retries = data["max_retries"]
        ultraplan = data["ultraplan"]

        if score >= 0.85:
            assert mode == "single", f"score={score} should be single, got {mode}"
            assert max_retries == 0
        elif score >= 0.70:
            assert mode == "multi_reduced", f"score={score} should be multi_reduced, got {mode}"
            assert max_retries == 3
        elif score >= 0.50:
            assert mode == "multi_full", f"score={score} should be multi_full, got {mode}"
            assert max_retries == 5
        else:
            assert mode == "multi_ultraplan", f"score={score} should be multi_ultraplan, got {mode}"
            assert max_retries == 5
            assert ultraplan is True

    @given(
        task=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "Z"),
                blacklist_characters="\x00'\"\\`$",
            ),
            min_size=1,
            max_size=100,
        ),
        module=st.sampled_from(VALID_MODULES),
    )
    @settings(max_examples=100)
    def test_output_has_required_fields(self, task, module):
        """Output JSON must contain all required fields."""
        assume(task.strip())
        data = run_confidence_trigger(task, module)

        required_keys = {"score", "dimensions", "mode", "max_retries", "ultraplan", "agent_team", "task", "module"}
        assert required_keys.issubset(data.keys()), (
            f"Missing keys: {required_keys - data.keys()}"
        )


# ── Property 5: Security tasks force full pipeline ──


class TestConfidenceTriggerSecurityForce:
    """Feature: harness-pipeline, Property 5: Confidence_Trigger enforces full pipeline for security tasks

    For any task description containing security-related keywords, the
    Confidence_Trigger SHALL produce a score below 0.70, forcing multi-agent
    pipeline execution.

    Validates: Requirements 9.7
    """

    @given(
        keyword=st.sampled_from(SECURITY_KEYWORDS),
        filler=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "Z"),
                blacklist_characters="\x00'\"\\`$",
            ),
            min_size=5,
            max_size=50,
        ),
        module=st.sampled_from(VALID_MODULES),
    )
    @settings(max_examples=100)
    def test_security_keywords_force_below_070(self, keyword, filler, module):
        """Tasks with security keywords must have score < 0.70."""
        task = f"{filler} {keyword} {filler}"
        data = run_confidence_trigger(task, module)

        assert data["score"] < 0.70, (
            f"Security task with keyword '{keyword}' got score {data['score']} >= 0.70. "
            f"Task: '{task}', Mode: {data['mode']}"
        )
        assert data["mode"] != "single", (
            f"Security task should not be in single mode. "
            f"Keyword: '{keyword}', Score: {data['score']}"
        )
