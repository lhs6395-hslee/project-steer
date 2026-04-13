"""Common fixtures for Harness Pipeline tests."""

import json
import os
import tempfile

import pytest

# ── Project paths ──

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
AGENTS_DIR = os.path.join(SCRIPTS_DIR, "agents")
SCHEMAS_DIR = os.path.join(PROJECT_ROOT, "schemas")


@pytest.fixture
def project_root():
    """Return the absolute path to the project root."""
    return PROJECT_ROOT


@pytest.fixture
def scripts_dir():
    """Return the absolute path to scripts/."""
    return SCRIPTS_DIR


@pytest.fixture
def agents_dir():
    """Return the absolute path to scripts/agents/."""
    return AGENTS_DIR


@pytest.fixture
def schemas_dir():
    """Return the absolute path to schemas/."""
    return SCHEMAS_DIR


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test artifacts."""
    return tmp_path


@pytest.fixture
def guardian_script():
    """Return the absolute path to guardian.sh."""
    return os.path.join(AGENTS_DIR, "guardian.sh")


@pytest.fixture
def load_schema(schemas_dir):
    """Factory fixture: load a JSON schema by name."""
    def _load(name: str) -> dict:
        path = os.path.join(schemas_dir, name)
        with open(path) as f:
            return json.load(f)
    return _load
