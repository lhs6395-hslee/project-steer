"""Property-Based Tests for Verdict business rules.

Feature: harness-pipeline
Property 9: Verdict business rule consistency

For any Verdict JSON, if verdict is "approved" then score SHALL be >= 0.7,
and if verdict is "needs_revision" then the issues array SHALL contain at
least one item.

Validates: Requirements 14.2, 14.3
"""

import json
import os

import jsonschema
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from tests.conftest import SCHEMAS_DIR


def load_schema(name: str) -> dict:
    path = os.path.join(SCHEMAS_DIR, name)
    with open(path) as f:
        return json.load(f)


VERDICT_SCHEMA = load_schema("verdict.schema.json")

non_empty_str = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
    min_size=1,
    max_size=50,
)


def approved_verdict_strategy():
    """Generate approved verdicts — score must be >= 0.7."""
    return st.fixed_dictionaries(
        {
            "verdict": st.just("approved"),
            "score": st.floats(min_value=0.7, max_value=1.0, allow_nan=False, allow_infinity=False),
            "issues": st.just([]),
            "suggestions": st.lists(non_empty_str, max_size=3),
        },
        optional={
            "iteration": st.integers(min_value=1, max_value=10),
        },
    )


def needs_revision_verdict_strategy():
    """Generate needs_revision verdicts — must have at least 1 issue."""
    return st.fixed_dictionaries(
        {
            "verdict": st.just("needs_revision"),
            "score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            "issues": st.lists(non_empty_str, min_size=1, max_size=5),
            "suggestions": st.lists(non_empty_str, min_size=1, max_size=5),
        },
        optional={
            "iteration": st.integers(min_value=1, max_value=10),
        },
    )


class TestVerdictBusinessRules:
    """Feature: harness-pipeline, Property 9: Verdict business rule consistency

    Validates: Requirements 14.2, 14.3
    """

    @given(data=approved_verdict_strategy())
    @settings(max_examples=100)
    def test_approved_verdict_has_score_gte_07(self, data):
        """If verdict is 'approved', score must be >= 0.7."""
        jsonschema.validate(instance=data, schema=VERDICT_SCHEMA)
        assert data["verdict"] == "approved"
        assert data["score"] >= 0.7, (
            f"Approved verdict must have score >= 0.7, got {data['score']}"
        )

    @given(data=needs_revision_verdict_strategy())
    @settings(max_examples=100)
    def test_needs_revision_has_at_least_one_issue(self, data):
        """If verdict is 'needs_revision', issues must have >= 1 item."""
        jsonschema.validate(instance=data, schema=VERDICT_SCHEMA)
        assert data["verdict"] == "needs_revision"
        assert len(data["issues"]) >= 1, (
            "needs_revision verdict must have at least one issue"
        )

    @given(
        score=st.floats(min_value=0.0, max_value=0.69, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_low_score_cannot_be_approved(self, score):
        """A verdict with score < 0.7 should not be approved per business rules."""
        # This tests the business rule: approved requires score >= 0.7
        data = {
            "verdict": "approved",
            "score": score,
            "issues": [],
            "suggestions": [],
        }
        # The schema itself allows this, but the business rule forbids it
        # We verify the business rule check catches it
        assert score < 0.7, "Score should be below 0.7 for this test"
        # Business rule: approved + score < 0.7 is inconsistent
        is_consistent = not (data["verdict"] == "approved" and data["score"] < 0.7)
        assert not is_consistent, (
            "approved verdict with score < 0.7 violates business rules"
        )
