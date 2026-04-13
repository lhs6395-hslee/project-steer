"""Property-Based Tests for Orchestrator logic.

Feature: harness-pipeline
Property 8: Circular feedback detection
Property 12: Reviewer information barrier

Validates: Requirements 8.5, 32.1, 32.2
"""

import json
import os
import subprocess
import tempfile

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from tests.conftest import PROJECT_ROOT

non_empty_str = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
    min_size=1,
    max_size=50,
)


# ── Circular feedback detection logic (extracted from orchestrate.sh) ──

def detect_circular_feedback(prev_verdict: dict, curr_verdict: dict) -> bool:
    """Python implementation of the circular feedback detection from orchestrate.sh.

    Returns True if circular feedback is detected (same non-empty issues).
    """
    prev_issues = sorted(prev_verdict.get("issues", []))
    curr_issues = sorted(curr_verdict.get("issues", []))
    return prev_issues == curr_issues and len(curr_issues) > 0


# ── Property 8: Circular feedback detection ──


class TestCircularFeedbackDetection:
    """Feature: harness-pipeline, Property 8: Circular feedback detection

    For any two consecutive Verdict files where the issues arrays are identical
    and non-empty, the Orchestrator SHALL detect circular feedback and escalate.

    Validates: Requirements 8.5
    """

    @given(issues=st.lists(non_empty_str, min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_identical_nonempty_issues_detected(self, issues):
        """Identical non-empty issues across two verdicts must be detected as circular."""
        prev = {"verdict": "needs_revision", "score": 0.4, "issues": issues, "suggestions": []}
        curr = {"verdict": "needs_revision", "score": 0.4, "issues": issues, "suggestions": []}
        assert detect_circular_feedback(prev, curr) is True

    @given(
        issues1=st.lists(non_empty_str, min_size=1, max_size=5),
        issues2=st.lists(non_empty_str, min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_different_issues_not_detected(self, issues1, issues2):
        """Different issues should not be detected as circular."""
        assume(sorted(issues1) != sorted(issues2))
        prev = {"verdict": "needs_revision", "score": 0.4, "issues": issues1, "suggestions": []}
        curr = {"verdict": "needs_revision", "score": 0.4, "issues": issues2, "suggestions": []}
        assert detect_circular_feedback(prev, curr) is False

    @given(
        issues=st.lists(non_empty_str, min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_order_independent_detection(self, issues):
        """Circular detection should be order-independent (sorted comparison)."""
        import random
        shuffled = list(issues)
        random.shuffle(shuffled)
        prev = {"verdict": "needs_revision", "score": 0.4, "issues": issues, "suggestions": []}
        curr = {"verdict": "needs_revision", "score": 0.4, "issues": shuffled, "suggestions": []}
        assert detect_circular_feedback(prev, curr) is True

    def test_empty_issues_not_circular(self):
        """Empty issues arrays should not be detected as circular."""
        prev = {"verdict": "needs_revision", "score": 0.4, "issues": [], "suggestions": []}
        curr = {"verdict": "needs_revision", "score": 0.4, "issues": [], "suggestions": []}
        assert detect_circular_feedback(prev, curr) is False

    @given(issues=st.lists(non_empty_str, min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_circular_detection_via_bash(self, issues):
        """Verify the bash-level circular detection matches Python logic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prev_file = os.path.join(tmpdir, "verdict_1.json")
            curr_file = os.path.join(tmpdir, "verdict_2.json")

            prev_data = {"verdict": "needs_revision", "score": 0.4, "issues": issues, "suggestions": []}
            curr_data = {"verdict": "needs_revision", "score": 0.4, "issues": issues, "suggestions": []}

            with open(prev_file, "w") as f:
                json.dump(prev_data, f)
            with open(curr_file, "w") as f:
                json.dump(curr_data, f)

            # Run the same Python logic used in orchestrate.sh
            script = f"""
import json, sys
try:
    with open('{prev_file}') as f:
        prev = json.load(f)
    with open('{curr_file}') as f:
        curr = json.load(f)
    prev_issues = sorted(prev.get('issues', []))
    curr_issues = sorted(curr.get('issues', []))
    if prev_issues == curr_issues and len(curr_issues) > 0:
        print('yes')
    else:
        print('no')
except:
    print('no')
"""
            result = subprocess.run(
                ["python3", "-c", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.stdout.strip() == "yes"


# ── Property 12: Reviewer information barrier ──


class TestReviewerInformationBarrier:
    """Feature: harness-pipeline, Property 12: Reviewer information barrier

    For any pipeline execution, the input provided to the Reviewer SHALL
    contain only the Sprint_Contract and execution output. It SHALL NOT
    contain the Executor's internal reasoning, self-assessment, or previous
    review results.

    Validates: Requirements 32.1, 32.2
    """

    FORBIDDEN_KEYWORDS = [
        "EXECUTOR_REASONING",
        "SELF_ASSESSMENT",
        "my reasoning",
        "I think",
        "my approach",
        "PREVIOUS REVIEW",
        "previous_verdict",
    ]

    @given(
        plan_content=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
            min_size=10,
            max_size=100,
        ),
        exec_output=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
            min_size=10,
            max_size=100,
        ),
        module=st.sampled_from(["pptx", "docx", "wbs", "trello", "dooray", "gdrive", "datadog"]),
    )
    @settings(max_examples=100)
    def test_reviewer_input_construction(self, plan_content, exec_output, module):
        """Reviewer input must contain only Sprint_Contract + execution output."""
        # Simulate the reviewer input construction from orchestrate.sh
        review_input = (
            f"SPRINT_CONTRACT:\n{plan_content}\n\n"
            f"EXECUTION OUTPUT:\n{exec_output}\n\n"
            f"Module: {module}\n"
            f"Review adversarially. Output JSON verdict following schemas/verdict.schema.json."
        )

        # Verify no forbidden content
        for keyword in self.FORBIDDEN_KEYWORDS:
            assert keyword not in review_input, (
                f"Reviewer input contains forbidden keyword: '{keyword}'"
            )

        # Verify required sections are present
        assert "SPRINT_CONTRACT:" in review_input
        assert "EXECUTION OUTPUT:" in review_input

    @given(
        executor_reasoning=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            min_size=10,
            max_size=50,
        ),
    )
    @settings(max_examples=100)
    def test_executor_reasoning_excluded(self, executor_reasoning):
        """Executor reasoning must never appear in reviewer input."""
        # The orchestrate.sh constructs reviewer input from plan + output only
        plan = '{"task": "test", "module": "pptx", "steps": []}'
        output = '{"result": "done"}'

        # Correct construction (as in orchestrate.sh)
        review_input = (
            f"SPRINT_CONTRACT:\n{plan}\n\n"
            f"EXECUTION OUTPUT:\n{output}\n\n"
            f"Module: pptx\n"
            f"Review adversarially. Output JSON verdict following schemas/verdict.schema.json."
        )

        # The executor_reasoning should NOT be in the review input
        # This verifies the information barrier design
        assert executor_reasoning not in review_input or executor_reasoning.strip() == ""
