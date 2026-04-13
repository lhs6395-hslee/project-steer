"""Property-Based Tests for Guardian agent.

Feature: harness-pipeline
Property 1: Guardian blocks all dangerous commands
Property 2: Guardian correctly classifies safe and warning commands

Validates: Requirements 5.2, 5.3, 5.5, 5.6
"""

import json
import subprocess

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from tests.conftest import AGENTS_DIR

GUARDIAN_SCRIPT = f"{AGENTS_DIR}/guardian.sh"

# ── Blocked patterns (exit 2) ──
BLOCK_PATTERNS = [
    "DROP DATABASE",
    "DROP SCHEMA",
    "kubectl delete namespace kube-system",
    "kubectl delete namespace kube-public",
    "kubectl delete namespace default",
    "rm -rf /",
    "rm -rf /usr",
    "rm -rf /etc",
    "rm -rf /var",
    "rm -rf /home",
    "rm -rf ~",
    "git push --force origin main",
    "git push -f origin master",
    "mkfs.ext4 /dev/sda1",
    "dd if=/dev/zero of=/dev/sda",
    "> /dev/sda",
    "chmod -R 777 /",
]

# ── Warning patterns (exit 0 + stderr) ──
WARN_PATTERNS = [
    "DROP TABLE users",
    "TRUNCATE TABLE logs",
    "kubectl delete pod my-pod",
    "docker compose down -v",
    "docker system prune",
    "git reset --hard HEAD",
    "git clean -fd",
    "rm -rf ./build",
]

# ── Safe commands (exit 0, no stderr warning) ──
SAFE_COMMANDS = [
    "ls -la",
    "echo hello",
    "cat README.md",
    "python3 --version",
    "git status",
    "npm install",
    "mkdir -p build",
    "cp file.txt backup/",
]


def run_guardian(command: str) -> subprocess.CompletedProcess:
    """Run guardian.sh with a JSON command payload via stdin."""
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", GUARDIAN_SCRIPT],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result


# ── Property 1: Guardian blocks all dangerous commands ──


class TestGuardianBlocksDangerous:
    """Feature: harness-pipeline, Property 1: Guardian blocks all dangerous commands

    For any shell command string that contains a blocked pattern,
    the Guardian SHALL return exit code 2 and output the block reason to stderr.

    Validates: Requirements 5.2, 5.5
    """

    @given(
        pattern=st.sampled_from(BLOCK_PATTERNS),
        prefix=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            min_size=0,
            max_size=20,
        ),
    )
    @settings(max_examples=100)
    def test_blocked_patterns_return_exit_2(self, pattern, prefix):
        """Any command containing a blocked pattern must be blocked (exit 2)."""
        command = f"{prefix} {pattern}".strip()
        result = run_guardian(command)
        assert result.returncode == 2, (
            f"Expected exit 2 for blocked command '{command}', "
            f"got {result.returncode}. stderr: {result.stderr}"
        )

    @given(pattern=st.sampled_from(BLOCK_PATTERNS))
    @settings(max_examples=100)
    def test_blocked_patterns_emit_stderr(self, pattern):
        """Blocked commands must output a reason to stderr."""
        result = run_guardian(pattern)
        assert result.returncode == 2
        assert len(result.stderr.strip()) > 0, (
            f"Expected stderr output for blocked command '{pattern}'"
        )


# ── Property 2: Guardian correctly classifies safe and warning commands ──


class TestGuardianClassifiesSafeAndWarning:
    """Feature: harness-pipeline, Property 2: Guardian correctly classifies safe and warning commands

    For any shell command string that does not match any blocked pattern,
    the Guardian SHALL return exit code 0. Additionally, for any command
    matching a warning pattern, the Guardian SHALL output a warning message
    to stderr while still returning exit code 0.

    Validates: Requirements 5.3, 5.6
    """

    @given(command=st.sampled_from(SAFE_COMMANDS))
    @settings(max_examples=100)
    def test_safe_commands_return_exit_0(self, command):
        """Safe commands must be allowed (exit 0)."""
        result = run_guardian(command)
        assert result.returncode == 0, (
            f"Expected exit 0 for safe command '{command}', "
            f"got {result.returncode}. stderr: {result.stderr}"
        )

    @given(command=st.sampled_from(WARN_PATTERNS))
    @settings(max_examples=100)
    def test_warning_commands_return_exit_0_with_stderr(self, command):
        """Warning commands must return exit 0 but emit stderr warning."""
        result = run_guardian(command)
        assert result.returncode == 0, (
            f"Expected exit 0 for warning command '{command}', "
            f"got {result.returncode}"
        )
        assert "WARNING" in result.stderr or "warning" in result.stderr.lower(), (
            f"Expected warning in stderr for '{command}', got: {result.stderr}"
        )

    @given(
        word=st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=3,
            max_size=15,
        )
    )
    @settings(max_examples=100)
    def test_random_safe_text_returns_exit_0(self, word):
        """Random alphabetic text should never be blocked."""
        # Ensure the random word doesn't accidentally match patterns
        assume("drop" not in word.lower())
        assume("rm" not in word.lower())
        assume("kubectl" not in word.lower())
        assume("git" not in word.lower())
        assume("mkfs" not in word.lower())
        assume("dd" not in word.lower())
        assume("chmod" not in word.lower())
        assume("truncate" not in word.lower())
        assume("docker" not in word.lower())
        command = f"echo {word}"
        result = run_guardian(command)
        assert result.returncode == 0, (
            f"Expected exit 0 for safe command '{command}', "
            f"got {result.returncode}"
        )
