"""JSON Schema round-trip validation utilities and tests.

Tests that all three schemas (sprint_contract, verdict, handoff_file)
correctly validate conforming data and preserve structure through
JSON serialize/deserialize round-trips.

Validates: Requirements 6.7, 13.5, 14.5
"""

import json
import os

import jsonschema
import pytest

from tests.conftest import SCHEMAS_DIR


def load_schema(name: str) -> dict:
    """Load a JSON schema by filename."""
    path = os.path.join(SCHEMAS_DIR, name)
    with open(path) as f:
        return json.load(f)


def validate_round_trip(data: dict, schema: dict) -> None:
    """Validate that data conforms to schema and survives a round-trip.

    1. Validate data against schema
    2. Serialize to JSON string
    3. Deserialize back
    4. Assert structural equality
    """
    jsonschema.validate(instance=data, schema=schema)
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
    deserialized = json.loads(serialized)
    assert deserialized == data, "Round-trip produced different structure"


# ── Sprint Contract ──

SPRINT_CONTRACT_SCHEMA = load_schema("sprint_contract.schema.json")


class TestSprintContractRoundTrip:
    """Round-trip tests for sprint_contract.schema.json."""

    def test_minimal_valid(self):
        data = {
            "task": "Create presentation",
            "module": "pptx",
            "steps": [
                {"id": 1, "action": "Create slides", "acceptance_criteria": ["Slides exist"]}
            ],
            "acceptance_criteria": ["Presentation created"],
            "risks": ["Template missing"],
        }
        validate_round_trip(data, SPRINT_CONTRACT_SCHEMA)

    def test_full_fields(self):
        data = {
            "task": "주간 보고 생성",
            "module": "dooray",
            "steps": [
                {
                    "id": 1,
                    "action": "Collect data",
                    "dependencies": [],
                    "acceptance_criteria": ["Data collected"],
                    "estimated_complexity": "low",
                },
                {
                    "id": 2,
                    "action": "Generate report",
                    "dependencies": [1],
                    "acceptance_criteria": ["Report generated", "Format correct"],
                    "estimated_complexity": "medium",
                },
            ],
            "acceptance_criteria": ["Report complete", "Data accurate"],
            "constraints": ["Use Korean", "Max 5 pages"],
            "risks": ["API timeout", "Data inconsistency"],
        }
        validate_round_trip(data, SPRINT_CONTRACT_SCHEMA)

    def test_all_modules(self):
        for module in ["pptx", "docx", "wbs", "trello", "dooray", "gdrive", "datadog"]:
            data = {
                "task": f"Task for {module}",
                "module": module,
                "steps": [{"id": 1, "action": "Do work", "acceptance_criteria": ["Done"]}],
                "acceptance_criteria": ["Complete"],
                "risks": ["None identified"],
            }
            validate_round_trip(data, SPRINT_CONTRACT_SCHEMA)


# ── Verdict ──

VERDICT_SCHEMA = load_schema("verdict.schema.json")


class TestVerdictRoundTrip:
    """Round-trip tests for verdict.schema.json."""

    def test_approved_verdict(self):
        data = {
            "verdict": "approved",
            "score": 0.85,
            "issues": [],
            "suggestions": ["Consider adding more detail"],
        }
        validate_round_trip(data, VERDICT_SCHEMA)

    def test_needs_revision_verdict(self):
        data = {
            "verdict": "needs_revision",
            "score": 0.45,
            "checklist_results": {"format": True, "content": False},
            "issues": ["Missing section 3", "Incorrect data in table"],
            "suggestions": ["Add section 3", "Verify data source"],
            "iteration": 2,
        }
        validate_round_trip(data, VERDICT_SCHEMA)

    def test_rejected_verdict(self):
        data = {
            "verdict": "rejected",
            "score": 0.1,
            "issues": ["Fundamental approach is wrong"],
            "suggestions": ["Redesign from scratch"],
            "iteration": 1,
        }
        validate_round_trip(data, VERDICT_SCHEMA)


# ── Handoff File ──

HANDOFF_SCHEMA = load_schema("handoff_file.schema.json")


class TestHandoffFileRoundTrip:
    """Round-trip tests for handoff_file.schema.json."""

    def test_minimal_handoff(self):
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00Z",
            "from_agent": "orchestrator",
            "to_agent": "planner",
            "status": "pending",
            "payload": {"task": "Create report", "module": "pptx"},
        }
        validate_round_trip(data, HANDOFF_SCHEMA)

    def test_completed_with_tokens(self):
        data = {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "timestamp": "2025-01-15T11:00:00Z",
            "from_agent": "executor",
            "to_agent": "reviewer",
            "status": "completed",
            "iteration": 1,
            "token_usage": {
                "input_tokens": 1500,
                "output_tokens": 800,
                "estimated_cost_usd": 0.0165,
            },
            "payload": {"output_file": "results/output.json"},
        }
        validate_round_trip(data, HANDOFF_SCHEMA)

    def test_failed_handoff(self):
        data = {
            "id": "deadbeef-dead-beef-dead-beefdeadbeef",
            "timestamp": "2025-01-15T12:00:00Z",
            "from_agent": "guardian",
            "to_agent": "orchestrator",
            "status": "failed",
            "iteration": 0,
            "payload": {"error": "Blocked dangerous command", "command": "rm -rf /"},
        }
        validate_round_trip(data, HANDOFF_SCHEMA)
