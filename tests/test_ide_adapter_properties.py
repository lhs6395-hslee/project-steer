"""Property-Based Tests for IDE_Adapter and Atomic_Write.

Feature: harness-pipeline
Property 6: IDE_Adapter detection and path mapping consistency
Property 7: Atomic_Write produces correct file content

Validates: Requirements 10.1, 10.2, 10.5, 6.6, 10.4
"""

import os
import subprocess
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import AGENTS_DIR, PROJECT_ROOT

IDE_ADAPTER_SCRIPT = f"{AGENTS_DIR}/ide_adapter.sh"

# ── IDE → expected path mapping ──
IDE_PATH_MAP = {
    "claude_code": {
        "AGENT_DIR": ".pipeline",
        "HOOKS_DIR": ".claude/hooks",
        "STEERING_DIR": ".",
        "CONFIG_FILE": "CLAUDE.md",
        "MCP_FILE": ".mcp.json",
    },
    "kiro": {
        "AGENT_DIR": ".pipeline",
        "HOOKS_DIR": ".kiro/hooks",
        "STEERING_DIR": ".kiro/steering",
        "CONFIG_FILE": "AGENTS.md",
        "MCP_FILE": ".kiro/settings/mcp.json",
    },
    "antigravity": {
        "AGENT_DIR": ".pipeline",
        "HOOKS_DIR": ".agent/workflows",
        "STEERING_DIR": ".agent/rules",
        "CONFIG_FILE": "AGENTS.md",
        "MCP_FILE": ".mcp.json",
    },
    "vscode": {
        "AGENT_DIR": ".pipeline",
        "HOOKS_DIR": ".vscode",
        "STEERING_DIR": ".vscode",
        "CONFIG_FILE": "AGENTS.md",
        "MCP_FILE": ".mcp.json",
    },
}

# Environment variable → IDE name mapping
IDE_ENV_VARS = {
    "claude_code": "CLAUDE_CODE",
    "kiro": "KIRO_IDE",
    "antigravity": "ANTIGRAVITY",
    "vscode": "VSCODE_PID",
}


def run_ide_adapter_detect(env_overrides: dict, cwd: str = None) -> dict:
    """Source ide_adapter.sh and print detected IDE + path variables.

    We override PATH to remove 'claude' CLI from detection, and clear
    all IDE env vars, so only the explicitly set env var determines IDE.
    """
    script = (
        f'source "{IDE_ADAPTER_SCRIPT}"\n'
        'echo "IDE_NAME=$IDE_NAME"\n'
        'echo "AGENT_DIR=$AGENT_DIR"\n'
        'echo "HOOKS_DIR=$HOOKS_DIR"\n'
        'echo "STEERING_DIR=$STEERING_DIR"\n'
        'echo "CONFIG_FILE=$CONFIG_FILE"\n'
        'echo "MCP_FILE=$MCP_FILE"\n'
    )
    env = os.environ.copy()
    # Clear all IDE env vars first
    for var in IDE_ENV_VARS.values():
        env.pop(var, None)
    # Remove claude CLI from PATH to prevent auto-detection as claude_code
    # unless we explicitly want claude_code
    if env_overrides.get("CLAUDE_CODE") is None:
        path_dirs = env.get("PATH", "").split(":")
        # Filter out dirs that contain claude binary
        filtered = [d for d in path_dirs if not _dir_has_claude(d)]
        env["PATH"] = ":".join(filtered) if filtered else "/usr/bin:/bin"
    env.update(env_overrides)

    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=cwd or PROJECT_ROOT,
    )
    parsed = {}
    for line in result.stdout.strip().split("\n"):
        if "=" in line:
            key, _, value = line.partition("=")
            parsed[key] = value
    return parsed, result.stderr


def _dir_has_claude(directory: str) -> bool:
    """Check if a directory contains a 'claude' executable."""
    try:
        return os.path.isfile(os.path.join(directory, "claude"))
    except (OSError, TypeError):
        return False


# ── Property 6: IDE_Adapter detection and path mapping consistency ──


class TestIDEAdapterDetection:
    """Feature: harness-pipeline, Property 6: IDE_Adapter detection and path mapping consistency

    For any combination of environment variables and directory existence,
    the IDE_Adapter SHALL detect exactly one IDE and map all path variables
    according to the defined mapping table.

    Validates: Requirements 10.1, 10.2, 10.5
    """

    @given(ide=st.sampled_from(list(IDE_ENV_VARS.keys())))
    @settings(max_examples=100)
    def test_env_var_detection_maps_correctly(self, ide):
        """Setting an IDE env var should detect that IDE and map paths correctly.

        We run in a temp dir to avoid .kiro/ or .vscode/ directory detection
        interfering with env-var-based detection.
        """
        env_var = IDE_ENV_VARS[ide]
        env = {env_var: "1"}
        with tempfile.TemporaryDirectory() as tmpdir:
            # For kiro test, create .kiro/ dir since env var alone triggers it
            if ide == "kiro":
                os.makedirs(os.path.join(tmpdir, ".kiro"), exist_ok=True)
            parsed, stderr = run_ide_adapter_detect(env, cwd=tmpdir)

            assert parsed.get("IDE_NAME") == ide, (
                f"Expected IDE '{ide}' with {env_var}=1, got '{parsed.get('IDE_NAME')}'"
            )
            expected = IDE_PATH_MAP[ide]
            for key, expected_val in expected.items():
                assert parsed.get(key) == expected_val, (
                    f"IDE={ide}: {key} expected '{expected_val}', got '{parsed.get(key)}'"
                )

    def test_default_fallback_to_kiro(self):
        """When no IDE is detected, should default to kiro with stderr warning."""
        # Run in a temp dir with no .kiro/, .vscode/, etc.
        # Also remove claude from PATH
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            for var in IDE_ENV_VARS.values():
                env.pop(var, None)
            path_dirs = env.get("PATH", "").split(":")
            filtered = [d for d in path_dirs if not _dir_has_claude(d)]
            env["PATH"] = ":".join(filtered) if filtered else "/usr/bin:/bin"

            script = (
                f'source "{IDE_ADAPTER_SCRIPT}"\n'
                'echo "IDE_NAME=$IDE_NAME"\n'
            )
            result = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
                cwd=tmpdir,
            )
            parsed = {}
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    key, _, value = line.partition("=")
                    parsed[key] = value
            assert parsed.get("IDE_NAME") == "kiro", (
                f"Expected default 'kiro', got '{parsed.get('IDE_NAME')}'"
            )
            assert "WARNING" in result.stderr or "warning" in result.stderr.lower() or "kiro" in result.stderr.lower(), (
                f"Expected warning in stderr for default fallback, got: {result.stderr}"
            )

    @given(ide=st.sampled_from(list(IDE_PATH_MAP.keys())))
    @settings(max_examples=100)
    def test_agent_dir_is_always_pipeline(self, ide):
        """AGENT_DIR should always be .pipeline regardless of IDE."""
        env_var = IDE_ENV_VARS[ide]
        env = {env_var: "1"}
        with tempfile.TemporaryDirectory() as tmpdir:
            if ide == "kiro":
                os.makedirs(os.path.join(tmpdir, ".kiro"), exist_ok=True)
            parsed, _ = run_ide_adapter_detect(env, cwd=tmpdir)
            assert parsed.get("AGENT_DIR") == ".pipeline"


# ── Property 7: Atomic_Write produces correct file content ──


class TestAtomicWrite:
    """Feature: harness-pipeline, Property 7: Atomic_Write produces correct file content

    For any target file path and content string, the atomic_write function
    SHALL produce a file at the target path containing exactly the provided
    content.

    Validates: Requirements 6.6, 10.4
    """

    @given(
        content=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "Z", "P"),
                blacklist_characters="\x00",
            ),
            min_size=1,
            max_size=200,
        ),
    )
    @settings(max_examples=100)
    def test_atomic_write_content_matches(self, content):
        """atomic_write should produce a file with exactly the given content + newline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test_output.txt")
            script = (
                f'source "{IDE_ADAPTER_SCRIPT}"\n'
                f'atomic_write "{target}" "$CONTENT"\n'
            )
            env = os.environ.copy()
            env["CONTENT"] = content
            result = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
                cwd=PROJECT_ROOT,
            )
            assert result.returncode == 0, f"atomic_write failed: {result.stderr}"
            assert os.path.isfile(target), f"File not created: {target}"
            with open(target) as f:
                file_content = f.read()
            # atomic_write uses printf '%s\n' which adds a trailing newline
            assert file_content == content + "\n", (
                f"Content mismatch. Expected {repr(content + chr(10))}, "
                f"got {repr(file_content)}"
            )

    @given(
        filename=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=100)
    def test_atomic_write_no_tmp_file_remains(self, filename):
        """After atomic_write, no .tmp files should remain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, f"{filename}.txt")
            script = (
                f'source "{IDE_ADAPTER_SCRIPT}"\n'
                f'atomic_write "{target}" "test content"\n'
            )
            result = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            assert result.returncode == 0
            # Check no .tmp files remain
            remaining = [f for f in os.listdir(tmpdir) if ".tmp." in f]
            assert len(remaining) == 0, f"Temp files remain: {remaining}"
