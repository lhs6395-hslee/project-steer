"""Property-Based Tests for KAIROS credential pattern detection.

Feature: harness-pipeline
Property 11: KAIROS credential pattern detection

For any file containing a string matching the pattern
(api_key|api_secret|password|token)\\s*[:=]\\s*["'][A-Za-z0-9],
the KAIROS monitor SHALL report at least one issue with severity "warn".

Validates: Requirements 18.3
"""

import json
import os
import subprocess
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import AGENTS_DIR, PROJECT_ROOT

KAIROS_SCRIPT = f"{AGENTS_DIR}/kairos.sh"

CREDENTIAL_KEYS = ["api_key", "api_secret", "password", "token"]
SEPARATORS = [": ", "= ", ":", "="]
QUOTE_CHARS = ['"', "'"]


def run_kairos(file_path: str) -> subprocess.CompletedProcess:
    """Run kairos.sh on a file."""
    env = os.environ.copy()
    # Ensure .pipeline/suggestions/ exists
    env.setdefault("AGENT_DIR", ".pipeline")
    result = subprocess.run(
        ["bash", KAIROS_SCRIPT, file_path],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=PROJECT_ROOT,
        env=env,
    )
    return result


class TestKAIROSCredentialDetection:
    """Feature: harness-pipeline, Property 11: KAIROS credential pattern detection

    For any file containing a credential pattern, the KAIROS monitor SHALL
    report at least one issue with severity "warn".

    Validates: Requirements 18.3
    """

    @given(
        key=st.sampled_from(CREDENTIAL_KEYS),
        separator=st.sampled_from(SEPARATORS),
        quote=st.sampled_from(QUOTE_CHARS),
        value=st.from_regex(r"[A-Za-z0-9]{8,30}", fullmatch=True),
    )
    @settings(max_examples=100)
    def test_credential_pattern_detected(self, key, separator, quote, value):
        """Files with credential patterns must trigger a warn issue."""
        content = f'{key}{separator}{quote}{value}{quote}\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
        ) as f:
            f.write(content)
            f.flush()
            tmp_path = f.name

        try:
            result = run_kairos(tmp_path)
            # KAIROS should detect the credential and output JSON with severity=warn
            assert result.returncode == 0, (
                f"KAIROS failed with exit {result.returncode}: {result.stderr}"
            )
            # Parse the JSON output
            stdout = result.stdout.strip()
            if stdout.startswith("{"):
                data = json.loads(stdout)
                assert data.get("severity") == "warn", (
                    f"Expected severity 'warn', got '{data.get('severity')}'"
                )
                assert len(data.get("issues", [])) >= 1, (
                    f"Expected at least 1 issue, got {data.get('issues')}"
                )
            else:
                # If no JSON output, the credential was not detected — fail
                assert False, (
                    f"KAIROS did not detect credential pattern '{key}{separator}{quote}{value}'. "
                    f"Output: {stdout}"
                )
        finally:
            os.unlink(tmp_path)

    @given(
        safe_content=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            min_size=10,
            max_size=100,
        ),
    )
    @settings(max_examples=100)
    def test_safe_files_no_credential_warning(self, safe_content):
        """Files without credential patterns should not trigger credential warnings."""
        # Ensure content doesn't accidentally match credential patterns
        content = f"# Safe file\n{safe_content}\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, dir=tempfile.gettempdir()
        ) as f:
            f.write(content)
            f.flush()
            tmp_path = f.name

        try:
            result = run_kairos(tmp_path)
            stdout = result.stdout.strip()
            if stdout.startswith("{"):
                data = json.loads(stdout)
                # If issues found, they should not be about credentials
                issues = data.get("issues", [])
                for issue in issues:
                    assert "credential" not in issue.lower() or any(
                        kw in content.lower()
                        for kw in ["api_key", "api_secret", "password", "token"]
                    )
        finally:
            os.unlink(tmp_path)
